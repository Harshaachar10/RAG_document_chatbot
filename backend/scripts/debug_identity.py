from pathlib import Path

from app.identity.pipeline import run_identity_pipeline

r = run_identity_pipeline(Path("data"))
m = r["metrics"]
print("DOCTORS", m["doctors"], "with npi", m["doctors_with_npi"], "provisional", m["provisional_people"])
print("LEGACY", m["legacy_rows"], "merges", m["merges"], "splits", m["splits"], "new", m["new_masters"], m["new_master_names"])
print("NPI", m["npi_counts"])
print("DUP", m["duplicate_rows"], "CONFLICT", m["conflicting_duplicate_ids"])
print("CLAIMS bad", m["claim_invalid_or_placeholder"], "recovered", m["claim_recovered"])
print("OUTCOMES", m["outcomes"])
print("ACTIONS", m["actions"])
print("--- GOLDENS ---")
for g in r["golden_records"]:
    print(
        g["master_hcp_id"],
        g["npi"],
        g["npi_status"],
        g["display_name"],
        "|",
        g["specialty"],
        "|",
        g["organization"],
        "|",
        g["city"],
        g["state"],
        "members",
        g["member_count"],
    )
print("--- KEY ---")
want = [
    "P-3301", "P-3302", "P-3303", "P-3304", "P-3305", "P-3306", "P-3307", "P-3308",
    "P-3309", "P-3310", "P-3311", "P-3312", "P-3313", "P-3314", "P-3315", "P-3316", "P-3317",
    "CLM-55104", "CLM-55122", "CLM-55127", "CLM-55124", "CLM-55128", "CLM-55103", "CLM-55123",
    "CLM-55129", "CLM-55102", "CLM-55106", "CLM-55109", "CLM-55112", "E-1142", "E-1143",
    "HUB-0013", "HUB-0006", "CRM-9401", "CRM-9602", "CRM-9622", "CRM-9623", "CRM-7781",
    "CRM-9621", "N-0001", "N-0002", "N-0003", "N-0004", "N-0005", "N-0006", "N-0007",
    "N-0008", "N-0009", "N-0010", "N-0011", "N-0012", "M1001", "M1005", "M1006", "M1018", "M2044",
]
by = {}
for d in r["decisions"]:
    by.setdefault(d["record_id"].split("#dup")[0], []).append(d)
for rid in want:
    rows = by.get(rid, [])
    if not rows:
        print(rid, "MISSING")
        continue
    for d in rows:
        label = str(d.get("target_label") or "")[:32]
        reason = (d.get("reason") or "")[:90]
        print(f"{d['record_id']:18} {d['action']:20} {str(d.get('npi_status')):12} {label:32} {d.get('score')} {reason}")
print("--- MISMATCHES ---")
for d in r["decisions"]:
    if d.get("npi_status") == "MISMATCH":
        print(d["record_id"], d["action"], d.get("target_label"), d.get("npi_conflict"), d.get("npi_owner_name"))
print("--- GROUP ---")
for d in r["decisions"]:
    if d.get("npi_status") == "GROUP_NPI":
        print(d["record_id"], d["action"], d.get("target_label"))
print("--- UNMATCHED ---")
for d in r["decisions"]:
    if d["action"] == "UNMATCHED":
        print(d["record_id"], d.get("display_name"), d.get("reason"))
print("--- PROVISIONAL ---")
for d in r["decisions"]:
    if d["action"] == "PROVISIONAL":
        print(d["record_id"], d.get("target_label"), d.get("target_id"))
