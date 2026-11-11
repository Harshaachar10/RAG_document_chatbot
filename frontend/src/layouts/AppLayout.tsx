import { useQuery } from '@tanstack/react-query';
import { useCallback, useMemo, useState } from 'react';
import { NavLink, Outlet, useLocation, useNavigate, useSearchParams } from 'react-router-dom';
import { fetchHealth } from '../api/dashboard';
import { fetchReviewWorkspace } from '../api/reviews';
import { AskPanel } from '../components/AskPanel';
import { HowItWorksDrawer } from '../components/HowItWorksDrawer';
import { NAV_ITEMS } from '../config/navigation';
import { ShellContext } from './shell';

function statusDot(ready: boolean, local = false) {
  if (ready) return '#34c38f';
  if (local) return '#e0a100';
  return '#e06a62';
}

export function AppLayout() {
  const health = useQuery({ queryKey: ['health'], queryFn: ({ signal }) => fetchHealth(signal) });
  const pending = useQuery({
    queryKey: ['review-workspace'],
    queryFn: ({ signal }) => fetchReviewWorkspace(signal),
  });
  const location = useLocation();
  const navigate = useNavigate();
  const [params, setParams] = useSearchParams();
  const [subtitle, setSubtitleState] = useState('');
  const setSubtitle = useCallback((value: string) => {
    setSubtitleState((current) => (current === value ? current : value));
  }, []);
  const [askOpen, setAskOpen] = useState(false);
  const [askDoctor, setAskDoctor] = useState<string | undefined>();
  const [query, setQuery] = useState('');
  const howOpen = params.has('how');
  const howTab = params.get('how') || 'privacy';

  const title = useMemo(() => {
    if (location.pathname.startsWith('/doctors/')) return 'Golden record';
    if (location.pathname.startsWith('/doctors')) return 'Golden Records';
    if (location.pathname.startsWith('/review')) return 'Review';
    return 'Dashboard';
  }, [location.pathname]);

  const chatReady = Boolean(health.data?.chat_ready ?? health.data?.ai_ready);
  const embeddingsReady = Boolean(health.data?.embeddings_ready);
  const searchReady = Boolean(health.data?.search_ready);
  const searchLocal = health.data?.search_mode === 'local';

  const openAsk = useCallback((doctorId?: string) => {
    setAskDoctor(doctorId);
    setAskOpen(true);
  }, []);
  const openUpload = useCallback(() => navigate('/?upload=1'), [navigate]);
  const openHow = useCallback(
    (tab?: string) => {
      setParams((current) => {
        const next = new URLSearchParams(current);
        next.set('how', tab || 'privacy');
        return next;
      });
    },
    [setParams],
  );
  const shellApi = useMemo(
    () => ({ setSubtitle, openAsk, openUpload, openHow }),
    [setSubtitle, openAsk, openUpload, openHow],
  );

  return (
    <ShellContext.Provider value={shellApi}>
      <div className="app">
        <aside className="side">
          <div className="brand">
            <div className="brand-mark" aria-hidden>
              A
            </div>
            Affine Analytics
          </div>
          <div className="prod">
            <b>Doctor Intelligence</b>
            <span className="tag-syn">Synthetic data</span>
          </div>
          <nav className="nav" aria-label="Primary">
            {NAV_ITEMS.map((item) => (
              <NavLink key={item.to} to={item.to} end={item.to === '/'} className={({ isActive }) => (isActive ? 'on' : '')}>
                <item.icon size={18} aria-hidden />
                {item.label}
                {item.to === '/review' && pending.data?.waiting ? <span className="count">{pending.data.waiting}</span> : null}
              </NavLink>
            ))}
          </nav>
          <div className="sysstat" aria-label="System status">
            <b>System status</b>
            <div>
              <span className="dot" style={{ background: statusDot(chatReady) }} />
              Azure OpenAI · chat {chatReady ? '' : '· not configured'}
            </div>
            <div>
              <span className="dot" style={{ background: statusDot(embeddingsReady) }} />
              Azure OpenAI · embeddings {embeddingsReady ? '' : '· not configured'}
            </div>
            <div>
              <span className="dot" style={{ background: statusDot(searchReady, searchLocal) }} />
              {searchReady ? 'Azure AI Search' : 'Semantic search running locally (test mode)'}
            </div>
            <div className="faint">Private endpoints · no data retained</div>
          </div>
        </aside>
        <div className="main">
          <header className="top">
            <div>
              <h1>{title}</h1>
              <div className="sub">{subtitle}</div>
            </div>
            <div className="spacer" />
            <form
              className="gsearch"
              onSubmit={(event) => {
                event.preventDefault();
                const text = query.trim();
                if (text) navigate(`/doctors?search=${encodeURIComponent(text)}`);
              }}
            >
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden>
                <circle cx="11" cy="11" r="7" />
                <path d="m20 20-3.5-3.5" />
              </svg>
              <input
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                placeholder="Search doctors, NPIs, records"
                aria-label="Search doctors, NPIs and records"
              />
            </form>
            <button
              type="button"
              className="btn"
              onClick={() => {
                setParams((current) => {
                  const next = new URLSearchParams(current);
                  next.set('how', howTab);
                  return next;
                });
              }}
            >
              How it works
            </button>
            <button type="button" className="btn primary" onClick={() => setAskOpen(true)}>
              Ask
            </button>
          </header>
          <div className="view">
            <Outlet />
          </div>
        </div>
      </div>
      <HowItWorksDrawer
        open={howOpen}
        tab={howTab}
        onTab={(tab) => {
          setParams((current) => {
            const next = new URLSearchParams(current);
            next.set('how', tab);
            return next;
          });
        }}
        onOpenChange={(open) => {
          if (!open) {
            setParams((current) => {
              const next = new URLSearchParams(current);
              next.delete('how');
              return next;
            });
          }
        }}
      />
      {askOpen ? (
        <>
          <div className="dscrim" onClick={() => setAskOpen(false)} />
          <aside className="drawer" role="dialog" aria-modal="true" aria-label="Ask">
            <div className="drawer-h">
              <h2>{askDoctor ? 'Ask about this doctor' : 'Ask'}</h2>
              <button type="button" className="iconbtn x" aria-label="Close" onClick={() => setAskOpen(false)}>
                ×
              </button>
            </div>
            <div className="drawer-b">
              <AskPanel doctorId={askDoctor} title={askDoctor ? 'Ask about this doctor' : 'Ask'} />
            </div>
          </aside>
        </>
      ) : null}
    </ShellContext.Provider>
  );
}
