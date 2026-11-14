#!/usr/bin/env python3
"""
Co&Co Sort: UNDO the last sort run.

  python3 undo.py "/path/to/Sort me"

Moves every file back to its original name and place, then removes
folders the sort created if they are now empty. Works for a sort that
stopped halfway too. Files that are open in another app are kept on the
list, so running undo again after closing that app finishes the job.
"""
import json
import os
import sys
from pathlib import Path

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(errors="replace")
    except Exception:
        pass

PENDING = "undo-pending.jsonl"


# ---------- undo journal (same helpers live in apply.py) ----------

def load_runs(work):
    f = work / "undo.json"
    if not f.exists():
        return []
    try:
        return json.loads(f.read_text(encoding="utf-8") or "[]")
    except json.JSONDecodeError:
        return []


def save_runs(work, runs):
    tmp = work / "undo.json.tmp"
    tmp.write_text(json.dumps(runs, indent=1, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, work / "undo.json")


def recover_pending(work):
    """Fold the journal of a sort that stopped halfway into undo.json."""
    pend = work / PENDING
    if not pend.exists():
        return 0
    when, moves, cancelled = "earlier", [], set()
    for line in pend.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            m = json.loads(line)
        except json.JSONDecodeError:
            continue  # the last line may be half written
        if "when" in m:
            when = m["when"]
        elif "cancel" in m:
            cancelled.add(m["cancel"])
        elif "from" in m and "to" in m:
            moves.append(m)
    moves = [m for m in moves if m["from"] not in cancelled]
    if moves:
        runs = load_runs(work)
        runs.append({"when": f"{when} (stopped halfway)", "moves": moves})
        save_runs(work, runs)
    pend.unlink()
    return len(moves)


def main():
    if len(sys.argv) != 2:
        sys.exit('Usage: python3 undo.py "/path/to/Sort me"')
    root = Path(sys.argv[1]).expanduser().resolve()
    work = root / ".cosort"
    if work.is_dir():
        recover_pending(work)
    runs = load_runs(work)
    if not runs:
        sys.exit("Nothing to undo.")
    last = runs.pop()
    restored, folders, still_locked = 0, set(), []
    for m in reversed(last["moves"]):
        src, dest = root / m["from"], root / m["to"]
        if not src.exists():
            if dest.exists():
                continue  # already back (the sort stopped before moving it)
            print(f"missing, skipped: {m['from']}")
            continue
        if dest.exists():
            print(f"original name taken, skipped: {m['to']}")
            continue
        dest.parent.mkdir(parents=True, exist_ok=True)
        try:
            src.rename(dest)
        except OSError as e:
            print(f"in use, not restored yet: {m['from']} ({e.strerror or e})")
            still_locked.append(m)
            continue
        folders.add(src.parent)
        restored += 1
    for f in sorted(folders, key=lambda p: len(p.parts), reverse=True):
        try:
            f.rmdir()  # only succeeds when empty
        except OSError:
            pass
    if still_locked:
        runs.append({"when": last["when"], "moves": list(reversed(still_locked))})
    save_runs(work, runs)
    with open(root / "old names.txt", "a", encoding="utf-8") as fh:
        fh.write(f"\n# Undid the sort from {last['when']}: {restored} files restored\n")
    print(f"Restored {restored} files to their original names.")
    if still_locked:
        print(f"{len(still_locked)} file(s) are open in another app. Close it and run undo again to finish.")


if __name__ == "__main__":
    main()
