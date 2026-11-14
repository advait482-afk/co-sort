#!/usr/bin/env python3
"""
Co&Co Sort, step 1: PREP

Scans a "Sort me" folder and prepares everything Claude needs to look at,
without moving or changing a single file.

  python3 prep.py "/path/to/Sort me"

Creates a hidden work folder inside it:
  .cosort/manifest.json   one entry per file (type, size, date, duplicate, hints, transcript)
  .cosort/sheets/*.jpg    contact sheets: numbered tiles Claude reads visually
  .cosort/thumbs/*.jpg    one thumbnail per file (used later by the report)

Needs: Python 3.9+, Pillow, ffmpeg/ffprobe on PATH.
Optional: faster-whisper (speech to text). Without it, speech is detected by loudness only.
"""
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path

try:
    from PIL import Image, ImageDraw, ImageFont, ImageOps, ExifTags
except ImportError:
    sys.exit("Pillow is missing. Run: pip install pillow")

try:  # iPhone photos
    import pillow_heif  # type: ignore
    pillow_heif.register_heif_opener()
    HEIF = True
except Exception:
    HEIF = False

# Windows consoles are not UTF-8 by default: print "?" instead of crashing on
# file names in Kannada, Hindi or with emoji.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(errors="replace")
    except Exception:
        pass

VIDEO = {".mp4", ".mov", ".m4v", ".avi", ".mkv", ".webm", ".3gp", ".mts"}
PHOTO = {".jpg", ".jpeg", ".png", ".heic", ".heif", ".webp", ".gif", ".tif", ".tiff", ".bmp", ".dng"}
AUDIO = {".mp3", ".wav", ".m4a", ".aac", ".flac", ".ogg", ".aiff", ".aif", ".opus"}

WORK = ".cosort"
SKIP_NAMES = {"old names.txt", "sort-report.html", ".DS_Store", "Thumbs.db", "desktop.ini"}
TILE_W, TILE_H = 420, 300          # one tile on a contact sheet
SHEET_COLS, SHEET_ROWS = 4, 3      # 12 files per sheet keeps Claude's usage low
AUDIO_PROBE_SECONDS = 20           # "the start of each clip"


# ---------- helpers ----------

def run(cmd, timeout=120):
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8",
                           errors="replace", timeout=timeout)
        return r.returncode, r.stdout, r.stderr
    except Exception as e:  # noqa
        return 1, "", str(e)


def need(tool):
    if not shutil.which(tool):
        sys.exit(f"{tool} not found. Run the setup script for your computer first.")


def sha256(path, chunk=1 << 20):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(chunk), b""):
            h.update(block)
    return h.hexdigest()


def ffprobe(path):
    code, out, _ = run(["ffprobe", "-v", "error", "-print_format", "json",
                        "-show_format", "-show_streams", str(path)])
    if code:
        return {}
    try:
        return json.loads(out)
    except json.JSONDecodeError:
        return {}


def parse_date(s):
    if not s:
        return None
    for fmt in ("%Y:%m:%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S.%fZ", "%Y-%m-%dT%H:%M:%SZ",
                "%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(s.strip()[:26] if "%f" in fmt else s.strip(), fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    m = re.match(r"(\d{4})[-:](\d{2})[-:](\d{2})", s)
    return f"{m.group(1)}-{m.group(2)}-{m.group(3)}" if m else None


def mtime_date(path):
    return datetime.fromtimestamp(path.stat().st_mtime).strftime("%Y-%m-%d")


def font(size):
    for f in ("/System/Library/Fonts/Helvetica.ttc", "C:/Windows/Fonts/arialbd.ttf",
              "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"):
        if os.path.exists(f):
            try:
                return ImageFont.truetype(f, size)
            except Exception:
                pass
    return ImageFont.load_default()


# ---------- per type analysis ----------

def analyse_photo(path, thumb_out):
    info = {"width": None, "height": None, "camera": None, "date": None}
    try:
        im = Image.open(path)
        info["width"], info["height"] = im.size
        exif = {}
        try:
            raw = im.getexif()
            exif = {ExifTags.TAGS.get(k, k): v for k, v in raw.items()}
            sub = raw.get_ifd(0x8769) if hasattr(raw, "get_ifd") else {}
            exif.update({ExifTags.TAGS.get(k, k): v for k, v in sub.items()})
        except Exception:
            pass
        make, model = exif.get("Make"), exif.get("Model")
        if make or model:
            info["camera"] = f"{make or ''} {model or ''}".strip()
        info["date"] = parse_date(str(exif.get("DateTimeOriginal") or exif.get("DateTime") or ""))
        im = ImageOps.exif_transpose(im).convert("RGB")
        im.thumbnail((TILE_W, TILE_H))
        im.save(thumb_out, "JPEG", quality=82)
        return info, True
    except Exception:
        # HEIC without pillow-heif, RAW, etc: let ffmpeg try
        code, _, _ = run(["ffmpeg", "-y", "-v", "error", "-i", str(path), "-frames:v", "1",
                          "-vf", f"scale={TILE_W}:{TILE_H}:force_original_aspect_ratio=decrease",
                          str(thumb_out)])
        return info, code == 0 and thumb_out.exists()


def screenshot_hint(path, info):
    name = path.name.lower()
    if re.search(r"screen ?shot|screenshot|screen recording|scr_|whatsapp image", name):
        return True
    if path.suffix.lower() == ".png" and not info.get("camera"):
        return True
    return False


def audio_stats(path, start=0.0, seconds=AUDIO_PROBE_SECONDS):
    """Mean and max loudness over the first seconds, plus share of non-silent time."""
    code, _, err = run(["ffmpeg", "-v", "info", "-ss", str(start), "-t", str(seconds), "-i", str(path),
                        "-vn", "-af", "volumedetect,silencedetect=n=-35dB:d=0.4", "-f", "null", "-"])
    mean = re.search(r"mean_volume: (-?[\d.]+) dB", err)
    peak = re.search(r"max_volume: (-?[\d.]+) dB", err)
    silences = [float(x) for x in re.findall(r"silence_duration: ([\d.]+)", err)]
    if not mean:
        return {"has_audio": False}
    silent = min(sum(silences), seconds)
    return {"has_audio": True, "mean_db": float(mean.group(1)),
            "peak_db": float(peak.group(1)) if peak else None,
            "sound_ratio": round(1 - silent / seconds, 2)}


_WHISPER = None


def transcribe(path, seconds=AUDIO_PROBE_SECONDS):
    """Local speech to text on the start of the clip. Returns (text, language) or (None, None)."""
    global _WHISPER
    try:
        from faster_whisper import WhisperModel  # type: ignore
    except Exception:
        return None, None
    if _WHISPER is None:
        size = os.environ.get("COSORT_WHISPER", "base")
        _WHISPER = WhisperModel(size, device="auto", compute_type="int8")
    with tempfile.TemporaryDirectory() as td:
        wav = Path(td) / "a.wav"
        code, _, _ = run(["ffmpeg", "-y", "-v", "error", "-t", str(seconds), "-i", str(path),
                          "-vn", "-ac", "1", "-ar", "16000", str(wav)])
        if code or not wav.exists():
            return None, None
        segs, meta = _WHISPER.transcribe(str(wav), vad_filter=True, beam_size=1)
        text = " ".join(s.text.strip() for s in segs).strip()
        return (text or ""), meta.language


def analyse_video(path, thumb_out, frames_dir):
    meta = ffprobe(path)
    fmt = meta.get("format", {})
    v = next((s for s in meta.get("streams", []) if s.get("codec_type") == "video"), {})
    a = next((s for s in meta.get("streams", []) if s.get("codec_type") == "audio"), None)
    dur = float(fmt.get("duration") or v.get("duration") or 0)
    w, h = v.get("width"), v.get("height")
    rot = 0
    for sd in v.get("side_data_list", []) or []:
        if "rotation" in sd:
            rot = abs(int(sd["rotation"]))
    if rot in (90, 270) and w and h:
        w, h = h, w
    tags = {**fmt.get("tags", {}), **v.get("tags", {})}
    date = parse_date(tags.get("com.apple.quicktime.creationdate") or tags.get("creation_time") or "")

    # 3 frames: early, middle, late (skip the first half second of shake)
    frames = []
    points = [0.15, 0.5, 0.85] if dur > 1.5 else [0.5]
    for i, p in enumerate(points):
        out = frames_dir / f"{path.stem}_{i}.jpg"
        t = max(0.0, dur * p) if dur else 0
        code, _, _ = run(["ffmpeg", "-y", "-v", "error", "-ss", f"{t:.2f}", "-i", str(path),
                          "-frames:v", "1", "-vf", "scale=480:-2", str(out)])
        if code == 0 and out.exists():
            frames.append(out)
    ok = False
    if frames:
        strip = make_strip(frames)
        strip.thumbnail((TILE_W, TILE_H))
        strip.save(thumb_out, "JPEG", quality=82)
        ok = True
        Image.open(frames[len(frames) // 2]).convert("RGB").save(
            thumb_out.with_name(thumb_out.stem + "_cover.jpg"), "JPEG", quality=82)
    for f in frames:
        f.unlink(missing_ok=True)

    audio = audio_stats(path) if a else {"has_audio": False}
    text, lang = (transcribe(path) if a else (None, None))
    return {"duration": round(dur, 1), "width": w, "height": h,
            "orientation": "vertical" if (w and h and h > w) else "horizontal" if (w and h) else None,
            "date": date, "audio": audio, "transcript": text, "language": lang}, ok


def make_strip(frames):
    ims = [Image.open(f).convert("RGB") for f in frames]
    h = min(i.height for i in ims)
    ims = [i.resize((int(i.width * h / i.height), h)) for i in ims]
    strip = Image.new("RGB", (sum(i.width for i in ims) + 4 * (len(ims) - 1), h), "white")
    x = 0
    for i in ims:
        strip.paste(i, (x, 0))
        x += i.width + 4
    return strip


def analyse_audio(path, thumb_out):
    meta = ffprobe(path)
    fmt = meta.get("format", {})
    tags = {k.lower(): v for k, v in fmt.get("tags", {}).items()}
    dur = float(fmt.get("duration") or 0)
    stats = audio_stats(path)
    text, lang = transcribe(path)
    # simple waveform tile so audio files have a visual too
    code, _, _ = run(["ffmpeg", "-y", "-v", "error", "-t", "60", "-i", str(path), "-filter_complex",
                      f"showwavespic=s={TILE_W}x{TILE_H // 2}:colors=#a5466a", "-frames:v", "1", str(thumb_out)])
    return {"duration": round(dur, 1), "title": tags.get("title"), "artist": tags.get("artist"),
            "audio": stats, "transcript": text, "language": lang}, code == 0


# ---------- contact sheets ----------

def build_sheets(items, work):
    sheets_dir = work / "sheets"
    if sheets_dir.exists():
        shutil.rmtree(sheets_dir)
    sheets_dir.mkdir(parents=True)
    per = SHEET_COLS * SHEET_ROWS
    label_h = 46
    f_big, f_small = font(26), font(17)
    todo = [it for it in items if not it.get("duplicate_of")]
    for n in range(0, len(todo), per):
        batch = todo[n:n + per]
        sheet = Image.new("RGB", (SHEET_COLS * TILE_W, SHEET_ROWS * (TILE_H + label_h)), "white")
        d = ImageDraw.Draw(sheet)
        for i, it in enumerate(batch):
            x, y = (i % SHEET_COLS) * TILE_W, (i // SHEET_COLS) * (TILE_H + label_h)
            thumb = work / "thumbs" / f"{it['id']}.jpg"
            if thumb.exists():
                t = Image.open(thumb).convert("RGB")
                sheet.paste(t, (x + (TILE_W - t.width) // 2, y + (TILE_H - t.height) // 2))
            else:
                d.text((x + 20, y + TILE_H // 2), "no preview", fill="#999", font=f_small)
            d.rectangle([x, y + TILE_H, x + TILE_W - 1, y + TILE_H + label_h - 1], fill="#1c1418")
            d.text((x + 10, y + TILE_H + 10), f"#{it['id']}", fill="#ffffff", font=f_big)
            tag = it["kind"]
            if it["kind"] == "video":
                tag += f" {it.get('duration', 0)}s {it.get('orientation') or ''}"
            d.text((x + 110, y + TILE_H + 14), tag[:34], fill="#f0c9d7", font=f_small)
            d.rectangle([x, y, x + TILE_W - 1, y + TILE_H + label_h - 1], outline="#e5e5e5")
            it["sheet"] = f"sheets/sheet_{n // per + 1:03d}.jpg"
        sheet.save(sheets_dir / f"sheet_{n // per + 1:03d}.jpg", "JPEG", quality=80)
    return len(range(0, len(todo), per))


# ---------- main ----------

def main():
    if len(sys.argv) < 2:
        sys.exit('Usage: python3 prep.py "/path/to/Sort me"')
    root = Path(sys.argv[1]).expanduser().resolve()
    if not root.is_dir():
        sys.exit(f"Folder not found: {root}")
    need("ffmpeg")
    need("ffprobe")

    work = root / WORK
    if (work / "undo.json").exists() and json.loads((work / "undo.json").read_text(encoding="utf-8") or "[]"):
        print("Note: this folder was sorted before. Undo info for the earlier run is kept.")
    shutil.rmtree(work / "thumbs", ignore_errors=True)  # ids change between runs
    (work / "thumbs").mkdir(parents=True, exist_ok=True)
    frames_dir = work / "frames"
    frames_dir.mkdir(exist_ok=True)

    files = []
    for p in sorted(root.rglob("*")):
        rel = p.relative_to(root)
        if p.is_dir() or rel.parts[0] == WORK or p.name in SKIP_NAMES or p.name.startswith("._"):
            continue
        files.append(p)
    # originals before "IMG_1 (1).JPG" / "IMG_1 copy.JPG", so the copy is the one marked duplicate
    files.sort(key=lambda p: (bool(re.search(r"\(\d+\)|\bcopy\b| \d$", p.stem, re.I)), str(p)))

    items, seen_hash = [], {}
    for idx, p in enumerate(files, 1):
        ext = p.suffix.lower()
        kind = "video" if ext in VIDEO else "photo" if ext in PHOTO else "audio" if ext in AUDIO else "other"
        it = {"id": idx, "path": str(p.relative_to(root)), "name": p.name, "ext": ext,
              "kind": kind, "size_mb": round(p.stat().st_size / 1_048_576, 2)}
        digest = sha256(p)
        if digest in seen_hash:
            it["duplicate_of"] = seen_hash[digest]
        else:
            seen_hash[digest] = idx
        thumb = work / "thumbs" / f"{idx}.jpg"
        print(f"[{idx}/{len(files)}] {kind:5} {p.name}", flush=True)
        if it.get("duplicate_of"):
            pass  # no need to look at an identical file twice
        elif kind == "photo":
            info, _ = analyse_photo(p, thumb)
            it.update(info)
            it["screenshot_hint"] = screenshot_hint(p, info)
        elif kind == "video":
            info, _ = analyse_video(p, thumb, frames_dir)
            it.update(info)
        elif kind == "audio":
            info, _ = analyse_audio(p, thumb)
            it.update(info)
        it["date"] = it.get("date") or mtime_date(p)
        items.append(it)
    shutil.rmtree(frames_dir, ignore_errors=True)

    n_sheets = build_sheets(items, work)
    counts = {}
    for it in items:
        counts[it["kind"]] = counts.get(it["kind"], 0) + 1
    manifest = {"root": str(root), "created": datetime.now().isoformat(timespec="seconds"),
                "speech_to_text": bool(_WHISPER) or _has_whisper(), "counts": counts,
                "duplicates": sum(1 for i in items if i.get("duplicate_of")),
                "sheets": n_sheets, "items": items}
    (work / "manifest.json").write_text(json.dumps(manifest, indent=1, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({k: manifest[k] for k in ("counts", "duplicates", "sheets", "speech_to_text")}))
    print(f"Done. Manifest: {work / 'manifest.json'}")


def _has_whisper():
    try:
        import faster_whisper  # type: ignore  # noqa
        return True
    except Exception:
        return False


if __name__ == "__main__":
    main()
