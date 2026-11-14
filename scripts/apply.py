#!/usr/bin/env python3
"""
Co&Co Sort, step 3: APPLY

Carries out the plan Claude wrote. Renames and moves files inside the
"Sort me" folder only. Never deletes, never edits file contents.

  python3 apply.py "/path/to/Sort me" plan.json [--dry-run]

plan.json:
{
  "folders": ["Talking head", "B-roll", "Photos", ...],
  "files": [ {"id": 3, "folder": "Talking head", "name": "2026-10-12 morning intro to camera"} ]
}

Rules the script enforces on its own:
  * every file keeps its extension
  * duplicates go to "Duplicates" (named after the original's new name + " copy")
  * files Claude left out of the plan go to "Other"
  * name clashes get " 2", " 3"...
  * names Windows forbids (CON, NUL, AUX, COM1...) get " file" added
  * a file that is open in another app stays where it is, and the rest still sort
  * every move is written to a journal before it happens, so undo works even
    if the sort stops halfway (power cut, crash, laptop closed)
  * every move is logged in "old names.txt" and in .cosort/undo.json
Then writes sort-report.html in the folder.
"""
import base64
import html
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path

# Windows consoles are not UTF-8 by default: print "?" instead of crashing on
# file names in Kannada, Hindi or with emoji.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(errors="replace")
    except Exception:
        pass

WORK = ".cosort"
PENDING = "undo-pending.jsonl"
BAD = re.compile(r'[\\/:*?"<>|\x00-\x1f]')
RESERVED = re.compile(r"(con|prn|aux|nul|com[1-9]|lpt[1-9])", re.I)


def clean(s, limit=90):
    s = BAD.sub(" ", str(s)).strip().strip(".")
    s = re.sub(r"\s+", " ", s)
    s = s[:limit].strip() or "untitled"
    if RESERVED.fullmatch(s.split(".")[0].strip()):
        s += " file"
    return s


def unique(dest: Path, taken: set) -> Path:
    def free(p):
        return not p.exists() and str(p).lower() not in taken
    cand, n = dest, 2
    while not free(cand):
        cand = dest.with_name(f"{dest.stem} {n}{dest.suffix}")
        n += 1
    taken.add(str(cand).lower())
    return cand


# ---------- undo journal (same helpers live in undo.py) ----------

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


def journal_write(fh, entry):
    fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
    fh.flush()
    os.fsync(fh.fileno())


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    dry = "--dry-run" in sys.argv
    if len(args) != 2:
        sys.exit('Usage: python3 apply.py "/path/to/Sort me" plan.json [--dry-run]')
    root = Path(args[0]).expanduser().resolve()
    work = root / WORK
    manifest = json.loads((work / "manifest.json").read_text(encoding="utf-8"))
    plan = json.loads(Path(args[1]).expanduser().read_text(encoding="utf-8"))
    items = {it["id"]: it for it in manifest["items"]}

    planned = {}
    for f in plan.get("files", []):
        fid = int(f["id"])
        if fid not in items:
            print(f"warning: id {fid} is not in the manifest, skipped")
            continue
        planned[fid] = {"folder": clean(f.get("folder") or "Other", 60),
                        "name": clean(f.get("name") or Path(items[fid]["name"]).stem)}

    moves = []   # (item, folder, new_stem)
    for fid, it in items.items():
        if it.get("duplicate_of"):
            continue
        p = planned.get(fid, {"folder": "Other", "name": Path(it["name"]).stem})
        moves.append((it, p["folder"], p["name"]))
    new_stem = {it["id"]: stem for it, _, stem in moves}
    for fid, it in items.items():
        if it.get("duplicate_of"):
            moves.append((it, "Duplicates", new_stem.get(it["duplicate_of"], Path(it["name"]).stem) + " copy"))

    stamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    journal = names = None
    if not dry:
        recovered = recover_pending(work)
        if recovered:
            print(f"Note: an earlier sort stopped halfway. Its {recovered} moves are saved, so undo can still restore them.")
        journal = open(work / PENDING, "a", encoding="utf-8")
        journal_write(journal, {"when": stamp})
        names = open(root / "old names.txt", "a", encoding="utf-8")
        names.write(f"\n# Sorted {stamp}  (old name  ->  new name)\n")
        names.flush()

    log, undo, locked, taken = [], [], [], set()
    for it, folder, stem in moves:
        src = root / it["path"]
        if not src.exists():
            print(f"missing, skipped: {it['path']}")
            continue
        dest = unique(root / folder / f"{stem}{src.suffix}", taken)
        if src.resolve() == dest.resolve():
            continue
        # safety: never leave the Sort me folder
        if root not in dest.resolve().parents:
            print(f"refused unsafe path: {dest}")
            continue
        rel_new = str(dest.relative_to(root))
        line = f"{it['path']}  ->  {rel_new}"
        if dry:
            it["new_path"], it["folder"] = rel_new, folder
            log.append(line)
            print("[dry] " + line)
            continue
        dest.parent.mkdir(parents=True, exist_ok=True)
        entry = {"from": rel_new, "to": it["path"]}
        journal_write(journal, entry)  # logged before the move, so a crash can't lose it
        try:
            src.rename(dest)
        except OSError as e:
            # usually a file that is open in another app (Windows locks it)
            journal_write(journal, {"cancel": rel_new})
            locked.append(it["path"])
            print(f"in use, left in place: {it['path']} ({e.strerror or e})")
            continue
        it["new_path"], it["folder"] = rel_new, folder
        undo.append(entry)
        log.append(line)
        names.write(line + "\n")
        names.flush()
        print(line)

    if dry:
        print(f"\nDry run: {len(log)} files would move. Nothing was changed.")
        return

    names.close()
    journal.close()
    runs = load_runs(work)
    runs.append({"when": stamp, "moves": undo})
    save_runs(work, runs)
    (work / PENDING).unlink()
    (work / "manifest.json").write_text(json.dumps(manifest, indent=1, ensure_ascii=False), encoding="utf-8")

    write_report(root, work, manifest, [m[0] for m in moves])
    print(f"\nMoved {len(undo)} files. Log: old names.txt  Report: sort-report.html")
    if locked:
        print(f"{len(locked)} file(s) were open in another app and stayed where they were. "
              "Close that app and run the sort again to move them.")


def thumb_uri(work, it):
    fid = it.get("duplicate_of") or it["id"]
    for name in (f"{fid}_cover.jpg", f"{fid}.jpg"):
        t = work / "thumbs" / name
        if t.exists():
            return "data:image/jpeg;base64," + base64.b64encode(t.read_bytes()).decode()
    return ""


def write_report(root, work, manifest, moved):
    groups = {}
    for it in moved:
        if it.get("folder"):
            groups.setdefault(it["folder"], []).append(it)
    order = sorted(groups, key=lambda k: (k in ("Other", "Duplicates"), -len(groups[k])))
    c = manifest["counts"]
    stats = [("Total files", len(manifest["items"])), ("Videos", c.get("video", 0)),
             ("Photos", c.get("photo", 0)), ("Audio", c.get("audio", 0)),
             ("Folders", len(groups)), ("Duplicates", manifest.get("duplicates", 0))]
    e = html.escape
    cards = []
    for g in order:
        tiles = "".join(
            f'<figure><div class="ph">{f"<img loading=lazy src={chr(34)}{thumb_uri(work, it)}{chr(34)}>" if thumb_uri(work, it) else ""}'
            f'<span class="k">{e(it["kind"])}</span></div>'
            f'<figcaption title="was: {e(it["name"])}">{e(Path(it["new_path"]).name)}</figcaption></figure>'
            for it in groups[g])
        cards.append(f'<section class="card"><header><h2>{e(g)}</h2><b>{len(groups[g])}</b></header>'
                     f'<div class="grid">{tiles}</div></section>')
    stat_html = "".join(f'<div class="stat"><small>{e(k)}</small><strong>{v}</strong></div>' for k, v in stats)
    page = f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Sort Report</title>
<style>
:root{{--bg:#fbf7f8;--ink:#1c1418;--mute:#7a6a70;--line:#ece3e6;--accent:#a5466a;--card:#fff}}
@media (prefers-color-scheme:dark){{:root{{--bg:#151012;--ink:#f4ecef;--mute:#a8979d;--line:#2c2226;--card:#1d1619}}}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--ink);font:15px/1.45 -apple-system,Segoe UI,Inter,sans-serif}}
.wrap{{max-width:1180px;margin:0 auto;padding:40px 20px 80px}}
.eyebrow{{color:var(--accent);font-size:12px;letter-spacing:.14em;text-transform:uppercase;font-weight:600}}
h1{{font-size:clamp(28px,5vw,46px);letter-spacing:-.02em;margin:6px 0 4px}}h1 em{{font-family:Georgia,serif;color:var(--accent);font-weight:400}}
.sub{{color:var(--mute);margin:0 0 28px}}
.stats{{display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:1px;background:var(--line);border:1px solid var(--line);border-radius:16px;overflow:hidden;margin-bottom:32px}}
.stat{{background:var(--card);padding:16px 18px}}.stat small{{display:block;color:var(--mute);font-size:11px;letter-spacing:.1em;text-transform:uppercase}}.stat strong{{font-size:28px}}
.cards{{display:grid;grid-template-columns:repeat(auto-fill,minmax(320px,1fr));gap:18px}}
.card{{background:var(--card);border:1px solid var(--line);border-radius:18px;padding:16px}}
.card header{{display:flex;justify-content:space-between;align-items:baseline;margin-bottom:12px}}.card h2{{font-size:17px;margin:0}}.card header b{{color:var(--accent);font-size:20px}}
.grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(90px,1fr));gap:10px;max-height:420px;overflow:auto}}
figure{{margin:0}}.ph{{position:relative;aspect-ratio:1;border-radius:10px;overflow:hidden;background:var(--line)}}.ph img{{width:100%;height:100%;object-fit:cover;display:block}}
.k{{position:absolute;left:5px;bottom:5px;font-size:9px;text-transform:uppercase;letter-spacing:.08em;background:rgba(0,0,0,.55);color:#fff;padding:2px 5px;border-radius:5px}}
figcaption{{font-size:11px;color:var(--mute);margin-top:4px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}}
</style></head><body><div class="wrap">
<div class="eyebrow">Co&amp;Co Sort</div><h1>Sorted <em>{e(root.name)}</em></h1>
<p class="sub">{datetime.now().strftime("%d %b %Y, %H:%M")} · old names kept in "old names.txt" · nothing deleted</p>
<div class="stats">{stat_html}</div><div class="cards">{''.join(cards)}</div></div></body></html>"""
    (root / "sort-report.html").write_text(page, encoding="utf-8")


if __name__ == "__main__":
    main()
