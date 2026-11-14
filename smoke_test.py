#!/usr/bin/env python3
"""
Smoke test for Co&Co Sort.

Builds a small fake shoot in a temporary folder, then checks that:
  1. prep.py writes a manifest and contact sheets without touching any file
  2. apply.py --dry-run changes nothing
  3. apply.py moves every file into a folder, keeps every byte, and logs old names
  4. undo.py puts every file back under its original name

Needs Python 3.9+, Pillow and ffmpeg on PATH. No AI model is involved:
the test writes plan.json itself, the way an agent would.

  python3 tests/smoke_test.py
"""
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"
PY = sys.executable
WORK = ".cosort"


def run(*args):
    result = subprocess.run(
        [PY, *map(str, args)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if result.returncode != 0:
        print(result.stdout)
        print(result.stderr)
        raise SystemExit(f"FAILED: {' '.join(map(str, args))}")
    return result.stdout


def ffmpeg(*args):
    subprocess.run(
        ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", *args],
        check=True,
    )


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def media_files(folder):
    """Every file the user owns: everything except the sorter's own outputs."""
    out = {}
    for p in Path(folder).rglob("*"):
        if not p.is_file():
            continue
        rel = p.relative_to(folder)
        if rel.parts[0] == WORK or rel.name in ("old names.txt", "sort-report.html"):
            continue
        out[str(rel)] = sha(p)
    return out


def make_shoot(folder):
    from PIL import Image, ImageDraw

    folder.mkdir(parents=True)
    # Two landscape clips with a tone, one vertical silent clip
    ffmpeg("-f", "lavfi", "-i", "testsrc=size=640x360:rate=25:duration=3",
           "-f", "lavfi", "-i", "sine=frequency=440:duration=3",
           "-shortest", "-pix_fmt", "yuv420p", str(folder / "IMG_0001.MOV"))
    ffmpeg("-f", "lavfi", "-i", "smptebars=size=640x360:rate=25:duration=2",
           "-pix_fmt", "yuv420p", str(folder / "IMG_0002.MOV"))
    ffmpeg("-f", "lavfi", "-i", "testsrc2=size=360x640:rate=25:duration=2",
           "-pix_fmt", "yuv420p", str(folder / "IMG_0003.mp4"))
    # Exact duplicate of the first clip
    shutil.copy2(folder / "IMG_0001.MOV", folder / "IMG_0001 copy.MOV")
    # A photo, a screenshot-like image, and a file with a non-English name
    img = Image.new("RGB", (800, 600), (200, 120, 60))
    ImageDraw.Draw(img).ellipse((200, 150, 600, 450), fill=(30, 90, 160))
    img.save(folder / "IMG_0004.jpg", quality=90)
    shot = Image.new("RGB", (1170, 2532), (255, 255, 255))
    ImageDraw.Draw(shot).rectangle((0, 0, 1170, 140), fill=(0, 122, 255))
    shot.save(folder / "Screenshot 2026-10-12 at 10.15.00.png")
    ImageDraw.Draw(img).rectangle((50, 50, 250, 250), fill=(240, 220, 40))
    img.save(folder / "ಬೆಂಗಳೂರು ಫೋಟೋ.jpg", quality=90)
    # Short audio
    ffmpeg("-f", "lavfi", "-i", "sine=frequency=880:duration=2", str(folder / "beep.wav"))


def load_manifest(folder):
    data = json.loads((folder / WORK / "manifest.json").read_text(encoding="utf-8"))
    files = data["items"]
    assert files, "manifest has no files"
    return files


def make_plan(folder, files):
    names = {"video": "B-roll", "photo": "Photos", "audio": "Sounds"}
    plan = {"folders": ["B-roll", "Photos", "Sounds", "Other"], "files": []}
    for f in files:
        if f.get("duplicate_of"):
            continue
        plan["files"].append({
            "id": f["id"],
            "folder": names.get(f.get("kind"), "Other"),
            # two files share a name on purpose: the script must add " 2"
            "name": "2026-10-12 shared name" if f["id"] <= 2 else f"2026-10-12 test clip {f['id']}",
        })
        if "ಫೋಟೋ" in f["name"]:
            plan["files"][-1]["name"] = "2026-10-12 ಬೆಂಗಳೂರು ಫೋಟೋ"  # non-English new name
    # a name Windows forbids
    for entry, f in zip(plan["files"], [f for f in files if not f.get("duplicate_of")]):
        if f["name"] == "beep.wav":
            entry["name"] = "CON"
    path = folder / WORK / "plan.json"
    path.write_text(json.dumps(plan, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


# Runs apply.py with Path.rename patched, to fake a locked file or a crash.
PATCHED_APPLY = r"""
import pathlib, runpy, sys
apply_py, mode, target = sys.argv[1], sys.argv[2], sys.argv[3]
real = pathlib.Path.rename
calls = {"n": 0}
def fake(self, dest):
    if mode == "lock" and self.name == target:
        raise PermissionError(13, "The process cannot access the file because it is being used by another process")
    if mode == "crash" and calls["n"] >= int(target):
        raise KeyboardInterrupt("simulated power cut")
    calls["n"] += 1
    return real(self, dest)
pathlib.Path.rename = fake
sys.argv = [apply_py] + sys.argv[4:]
runpy.run_path(apply_py, run_name="__main__")
"""


def run_patched(mode, target, *args, expect_fail=False):
    result = subprocess.run(
        [PY, "-c", PATCHED_APPLY, str(SCRIPTS / "apply.py"), mode, str(target), *map(str, args)],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    if (result.returncode != 0) != expect_fail:
        print(result.stdout)
        print(result.stderr)
        raise SystemExit(f"FAILED: patched apply ({mode})")
    return result.stdout


def main():
    for tool in ("ffmpeg", "ffprobe"):
        if not shutil.which(tool):
            raise SystemExit(f"{tool} not found on PATH")

    tmp = Path(tempfile.mkdtemp(prefix="cosort-test-"))
    shoot = tmp / "Sort me"
    try:
        make_shoot(shoot)
        before = media_files(shoot)
        print(f"fake shoot: {len(before)} files")

        # 1. prep changes nothing
        run(SCRIPTS / "prep.py", shoot)
        assert media_files(shoot) == before, "prep changed user files"
        files = load_manifest(shoot)
        assert len(files) == len(before), f"manifest lists {len(files)} of {len(before)} files"
        sheets = list((shoot / WORK / "sheets").glob("*.jpg"))
        assert sheets, "no contact sheets"
        dupes = [f for f in files if f.get("duplicate_of")]
        assert dupes, "duplicate copy was not detected"
        print(f"prep ok: {len(files)} in manifest, {len(sheets)} sheet(s), {len(dupes)} duplicate(s)")

        plan = make_plan(shoot, files)

        # 2. dry run changes nothing
        run(SCRIPTS / "apply.py", shoot, plan, "--dry-run")
        assert media_files(shoot) == before, "dry run changed user files"
        print("dry run ok: nothing moved")

        # 3. apply keeps every byte and leaves nothing loose at the top
        run(SCRIPTS / "apply.py", shoot, plan)
        after = media_files(shoot)
        assert sorted(after.values()) == sorted(before.values()), "a file was lost or changed"
        loose = [k for k in after if os.sep not in k and "/" not in k]
        assert not loose, f"files left unsorted at the top: {loose}"
        assert (shoot / "old names.txt").exists(), "old names.txt missing"
        assert (shoot / "sort-report.html").exists(), "sort-report.html missing"
        stems = [Path(k).stem for k in after]
        assert "2026-10-12 shared name 2" in stems, "name clash did not get ' 2'"
        assert "CON file" in stems and "CON" not in stems, "reserved Windows name was not fixed"
        assert "2026-10-12 ಬೆಂಗಳೂರು ಫೋಟೋ" in stems, "non-English new name was lost"
        print(f"apply ok: {len(after)} files sorted, contents identical, clashes and reserved names handled")

        # 4. undo restores the original names
        run(SCRIPTS / "undo.py", shoot)
        assert media_files(shoot) == before, "undo did not restore every file to its original name"
        print("undo ok: original names restored")

        # 5. a file open in another app stays put and the rest still sort
        run(SCRIPTS / "prep.py", shoot)
        plan = make_plan(shoot, load_manifest(shoot))
        out = run_patched("lock", "IMG_0002.MOV", shoot, plan)
        assert "in use, left in place: IMG_0002.MOV" in out, "locked file was not reported"
        after = media_files(shoot)
        assert "IMG_0002.MOV" in after, "locked file should stay where it was"
        assert sorted(after.values()) == sorted(before.values()), "a file was lost around the locked one"
        assert len([k for k in after if os.sep not in k and "/" not in k]) == 1, "other files did not sort"
        run(SCRIPTS / "undo.py", shoot)
        assert media_files(shoot) == before, "undo after a locked file did not restore everything"
        print("locked file ok: left in place, rest sorted, undo clean")

        # 6. the sort stops halfway (power cut): undo still restores everything
        run(SCRIPTS / "prep.py", shoot)
        plan = make_plan(shoot, load_manifest(shoot))
        run_patched("crash", 3, shoot, plan, expect_fail=True)
        moved = [k for k in media_files(shoot) if os.sep in k or "/" in k]
        assert len(moved) == 3, f"expected 3 files moved before the crash, got {len(moved)}"
        run(SCRIPTS / "undo.py", shoot)
        assert media_files(shoot) == before, "undo after a crash did not restore everything"
        print("crash ok: stopped after 3 files, undo restored all of them")

        print("\nALL PASSED")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    main()
