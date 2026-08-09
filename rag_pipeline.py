"""
rag_pipeline.py
----------------
Same pattern as your notebooks (6__1-RAG_pipeline_.ipynb / 10_RAG_pipeline.ipynb):

Data => Documents => Chunks => Embeddings => Vector Store => Retrieval => LLM

Just swapped OpenAI/Groq for Gemini, and added an upload wrapper so a
website can hand in a PDF instead of reading a fixed folder.
"""

import os
import uuid

from langchain_community.document_loaders.pdf import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from sentence_transformers import SentenceTransformer
import chromadb

from langchain_google_genai import ChatGoogleGenerativeAI


# ---------------- Documents ----------------

def load_all_pdfs(folder_path="huli/pdfs"):
    num_docs = 0
    all_docs = []

    for filename in os.listdir(folder_path):
        if filename.lower().endswith(".pdf"):
            # complete file path
            pdf_path = os.path.join(folder_path, filename)

            loader = PyPDFLoader(pdf_path)
            doc = loader.load()

            all_docs.extend(doc)
            num_docs += 1

    print("total pdfs:", num_docs)
    print("total pages:", len(all_docs))
    return all_docs


# ---------------- Chunks ----------------

def split_docs(documents, chunk_size=500, chunk_overlap=50):
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap
    )

    chunked_docs = text_splitter.split_documents(documents)
    return chunked_docs


# ---------------- Embedding ----------------

class EmbeddingManager:
    def __init__(self, model_name="all-MiniLM-L6-v2"):
        self.model_name = model_name
        print("loading model....", self.model_name)
        self.model = SentenceTransformer(self.model_name)
        print("embedding dimensions=", self.model.get_sentence_embedding_dimension())

    def generate_embeddings(self, text):
        embeddings = self.model.encode(text, show_progress_bar=True)
        print("embeddings shape:", embeddings.shape)
        return embeddings


# ---------------- Vector Store ----------------

class VectorStoreManager:
    def __init__(self, persist_directory="data/vector_store", collection_name="pdf_documents"):
        self.collection_name = collection_name
        self.persist_directory = persist_directory
        self.collection = None
        self.client = None

        self._initialize_store()

    def _initialize_store(self):
        os.makedirs(self.persist_directory, exist_ok=True)

        # create a client
        self.client = chromadb.PersistentClient(path=self.persist_directory)

        # create the collection
        self.collection = self.client.get_or_create_collection(
            name=self.collection_name,
            metadata={
                "description": "vector store collection for pdf embeddings in RAG",
                "hnsw:space": "cosine"
            }
        )

        print("initialized the vector store with collection:", self.collection_name)
        print("docs in collection:", self.collection.count())

    def add_documents(self, documents, embeddings):
        if len(documents) != len(embeddings):
            raise ValueError("num of documents does not match num of embeddings")

        # store => ids, embedding, document, metadata
        ids = []
        all_metadata = []
        documents_content = []
        embeddings_list = []

        for i, (doc, embedding) in enumerate(zip(documents, embeddings)):
            doc_id = f"doc_{uuid.uuid4()}"
            ids.append(doc_id)

            metadata = dict(doc.metadata)
            metadata["doc_index"] = i
            metadata["content_length"] = len(doc.page_content)
            all_metadata.append(metadata)

            documents_content.append(doc.page_content)

            embeddings_list.append(embedding.tolist())

            self.collection.add(
                ids=ids,
                metadatas=all_metadata,
                documents=documents_content,
                embeddings=embeddings_list
            )

        print("total documents added in vector store=", len(documents_content))
        print("docs in collection:", self.collection.count())


# ---------------- Retrieval Pipeline ----------------

class RAGRetriever:
    def __init__(self, embedding_manager, vector_store):
        self.embedding_manager = embedding_manager
        self.vector_store = vector_store

    def retrieve(self, query, top_k=5, score_threshold=0.0):
        # query => embedding
        query_embeddings = self.embedding_manager.generate_embeddings([query])[0]

        # semantic search
        results = self.vector_store.collection.query(
            query_embeddings=[query_embeddings.tolist()],
            n_results=top_k
        )

        retrieved_docs = []

        if results["documents"] and results["documents"][0]:
            ids = results["ids"][0]
            metadatas = results["metadatas"][0]
            documents = results["documents"][0]
            distances = results["distances"][0]

            for i, (doc_id, metadata, document, distance) in enumerate(zip(ids, metadatas, documents, distances)):
                similarity_score = 1 - distance

                if similarity_score >= score_threshold:
                    retrieved_docs.append({
                        "id": doc_id,
                        "document": document,
                        "metadata": metadata,
                        "distance": distance,
                        "similarity_score": similarity_score,
                        "rank": i + 1
                    })

            print(f"retrieved {len(retrieved_docs)} documents")

        else:
            print("no documents found")

        return retrieved_docs


# ---------------- Integrate with LLM (Gemini) ----------------

API_KEY_GOOGLE = os.getenv("GOOGLE_API_KEY", "paste-your-api-key-here")


def get_gemini_llm():
    return ChatGoogleGenerativeAI(
        google_api_key=API_KEY_GOOGLE,
        model="gemini-3.5-flash-lite",
        temperature=0.1,
        max_tokens=1024
    )


# generate our retrieval-augmented output
def generate_output(query, retriever, llm, top_k=3):
    results = retriever.retrieve(query, top_k)

    context = "\n".join([doc["document"] for doc in results]) if results else ""

    if not context:
        print("we found no relevant context for the given query")
        return "I could not find this information in the document."

    # context + query
    prompt = f""" use given context to generate the answer for the query
                Context: {context}
                Query: {query} """

    response = llm.invoke(prompt)  # expecting a string as prompt

    content = response.content
    # Newer Gemini models can return content as a list of blocks
    # (text blocks, signature/thinking blocks, etc.) instead of a
    # plain string. Pull out just the text parts.
    if isinstance(content, list):
        text_parts = []
        for block in content:
            if isinstance(block, str):
                text_parts.append(block)
            elif isinstance(block, dict) and block.get("type") == "text":
                text_parts.append(block.get("text", ""))
        return "".join(text_parts).strip() or "I could not find this information in the document."

    return content


# ---------------- upload-friendly wrapper ----------------
# load_all_pdfs() reads every PDF sitting in a folder, same as your notebook.
# For a website, the PDF arrives as an upload, so this saves it into that
# same folder first, then runs the exact same steps your notebook runs:
# Data => Documents => Chunks => Embeddings => Vector Store

def process_uploaded_pdf(uploaded_file_bytes, filename, folder_path="huli/pdfs",
                          persist_directory="data/vector_store"):
    os.makedirs(folder_path, exist_ok=True)

    # clear old PDFs so each upload starts fresh
    for f in os.listdir(folder_path):
        if f.lower().endswith(".pdf"):
            os.remove(os.path.join(folder_path, f))

    save_path = os.path.join(folder_path, filename)
    with open(save_path, "wb") as f:
        f.write(uploaded_file_bytes)

    # Data => Documents
    all_pdf_documents = load_all_pdfs(folder_path)

    # Documents => Chunks
    chunks = split_docs(all_pdf_documents)

    # Chunks => Embeddings
    embedding_manager = EmbeddingManager()
    texts = [doc.page_content for doc in chunks]
    embeddings = embedding_manager.generate_embeddings(texts)

    # Embeddings => Vector Store (fresh collection per upload)
    vector_store = VectorStoreManager(
        persist_directory=persist_directory,
        collection_name=f"pdf_documents_{uuid.uuid4().hex[:8]}"
    )
    vector_store.add_documents(chunks, embeddings)

    rag_retriever = RAGRetriever(embedding_manager, vector_store)
    return rag_retriever


def answer_question(rag_retriever, question, top_k=4):
    llm = get_gemini_llm()
    return generate_output(question, rag_retriever, llm, top_k=top_k)