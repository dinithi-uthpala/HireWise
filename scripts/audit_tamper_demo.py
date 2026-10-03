"""Safe audit-log tamper demo for the viva.

Works on a COPY of the database, so your real data is never touched.

    python scripts/audit_tamper_demo.py
    python scripts/audit_tamper_demo.py --db path/to/other.db
"""
from __future__ import annotations

import argparse
import shutil
import sqlite3
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from backend.agents.agent3_responsible_decision.audit_chain import verify_chain  # noqa: E402


def load_rows(db_path: Path):
    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row
    try:
        cur = con.execute("SELECT id, candidate_id, actor, action, summary_json, prev_hash, "
                          "entry_hash, ts FROM auditlog ORDER BY id")
        return [SimpleNamespace(**dict(r)) for r in cur.fetchall()]
    finally:
        con.close()


def report(label: str, rows) -> bool:
    ok, bad_id = verify_chain(rows)
    if ok:
        print(f"  {label}: CHAIN VALID ({len(rows)} entries)")
    else:
        print(f"  {label}: TAMPERING DETECTED at audit entry id {bad_id}")
    return ok


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=str(ROOT / "data" / "hirewise.db"))
    args = ap.parse_args()
    src = Path(args.db)
    if not src.exists():
        print(f"Database not found: {src}")
        return 1

    with tempfile.TemporaryDirectory() as tmp:
        copy = Path(tmp) / "audit_demo_copy.db"
        shutil.copy(src, copy)
        rows = load_rows(copy)
        if len(rows) < 2:
            print("Need at least 2 audit entries. Upload a CV through the pipeline first.")
            return 1

        print("HireWise audit-log tamper demo (working on a temporary COPY)\n")
        print("Step 1 - the untouched log")
        report("copy", rows)

        victim = rows[len(rows) // 2]
        print(f"\nStep 2 - an attacker edits audit entry {victim.id} "
              f"({victim.actor} / {victim.action}) to change its content")
        con = sqlite3.connect(copy)
        con.execute("UPDATE auditlog SET summary_json = ? WHERE id = ?",
                    ('{"match_score": 100.0, "note": "edited by attacker"}', victim.id))
        con.commit()
        con.close()
        report("after edit", load_rows(copy))

        print(f"\nStep 3 - the attacker instead DELETES entry {victim.id} from a fresh copy")
        shutil.copy(src, copy)
        con = sqlite3.connect(copy)
        con.execute("DELETE FROM auditlog WHERE id = ?", (victim.id,))
        con.commit()
        con.close()
        report("after delete", load_rows(copy))

    print("\nYour real database was NOT modified.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
