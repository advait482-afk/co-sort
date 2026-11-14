---
name: "co-sort"
description: "Sort a messy shoot folder. Watches every video, photo and audio file, gives each a descriptive name and moves it into folders (talking head, voiceover, b-roll, photos, screenshots, music, sounds, or the user's own folders). Use when the user says \"sort\", \"sort my footage\", \"sort this shoot\", \"organise my folder\" or points at a folder of IMG_ files."
---

# Co&Co Sort

Turn a folder of `IMG_4821.MOV` files into named files in sensible folders.
Everything runs on the user's computer. Nothing is uploaded anywhere except what Claude itself looks at (the contact sheets). Nothing is ever deleted.

Scripts live in `scripts/` next to this file. Call them with the full path.

## 0. Before the first sort

**Mac or Windows?** The commands below say `python3`. On Windows use `python` instead (or `py -3` if `python` opens the Microsoft Store). Use the folder path exactly as Windows shows it, in double quotes, for example `"C:\Users\Asha\Desktop\Sort me"`.

Check the tools once: `ffmpeg -version`, `ffprobe -version`, `python3 -c "import PIL"`.
If anything is missing, run the setup script for the computer:
- Mac: `bash setup/install_mac.sh`
- Windows: `powershell -ExecutionPolicy Bypass -File setup\install_windows.ps1`

Speech to text (`faster-whisper`) is optional. Without it the sort still works and tells talking head from b-roll by loudness and by what is in the frame.

## 1. Ask one question

Ask which folder to sort (default: a folder called `Sort me` on the Desktop) and which folders they want, in one message:

> Which folders should I sort into? Say **default** for Talking head, Voiceover, B-roll, Photos, Screenshots, Music, Sounds. Or name your own, like "morning, cafe, outfit" or "day 1, day 2, day 3".

If the user already said both, do not ask. `Other` and `Duplicates` are always added by the script.

## 2. Prep

```
python3 "<skill>/scripts/prep.py" "<folder>"
```

This writes `<folder>/.cosort/manifest.json` and numbered contact sheets in `<folder>/.cosort/sheets/`.
Each tile shows the file number (`#12`), its type, and for videos the length and orientation. Videos are shown as a strip of three frames (start, middle, end).

## 3. Look and decide

1. Read `manifest.json`. Per file you get: `kind`, `duration`, `orientation`, `date`, `camera`, `screenshot_hint`, `audio.sound_ratio`, `audio.mean_db`, `transcript`, `duplicate_of`.
2. Open every contact sheet with the Read tool. Look at each tile.
3. Decide a folder and a new name for every file without `duplicate_of`.

### Default folders: how to decide

| Folder | Signals |
|---|---|
| Talking head | video, a person facing the camera in most frames, speech in the transcript or `sound_ratio` above about 0.5 |
| Voiceover | audio file or video where someone speaks but no face is to camera (hands, screen, scenery with speech) |
| B-roll | video with no one talking to camera: scenery, details, process, walking shots, ambient sound only |
| Photos | photo taken with a camera (`camera` set, or clearly a real scene) |
| Screenshots | `screenshot_hint` true, or the image is a phone or computer screen UI, chat, or text graphic |
| Music | audio with a title/artist tag, or longer than about 30 s of continuous sound and no speech |
| Sounds | short audio effects, ambience, single sounds |
| Other | anything that fits nowhere (the script also sends files you skip here) |

With custom folders, use what is in the frame and the transcript to match the user's words. When unsure between two folders, pick the more specific one; if truly unclear, use `Other`.

### Naming rules

- Pattern: `YYYY-MM-DD what is in it` using the manifest `date`, then 3 to 7 plain words.
  Examples: `2026-10-12 talking to camera about morning routine`, `2026-10-12 cafe latte art closeup`, `2026-10-13 sunset over paddy fields`.
- Use what is said for talking heads: the topic from the transcript is the best name.
- Lowercase, no extension (the script keeps the original one), no slashes, no emoji.
- Similar clips can share a name; the script adds ` 2`, ` 3` itself.

## 4. Write the plan

Write `<folder>/.cosort/plan.json`:

```json
{
  "folders": ["Talking head", "B-roll", "Photos"],
  "files": [
    {"id": 1, "folder": "Talking head", "name": "2026-10-12 intro about the retreat"},
    {"id": 2, "folder": "B-roll", "name": "2026-10-12 garden walkway slow pan"}
  ]
}
```

For large folders (more than about 150 files) work sheet by sheet and append to the plan as you go, so nothing is lost if the conversation hits a limit.

## 5. Check, then apply

Run a dry run first and show the user a short count per folder:

```
python3 "<skill>/scripts/apply.py" "<folder>" "<folder>/.cosort/plan.json" --dry-run
```

If the user said to just go ahead, skip the confirmation. Otherwise ask once ("Move these 214 files?") and then:

```
python3 "<skill>/scripts/apply.py" "<folder>" "<folder>/.cosort/plan.json"
```

The script:
- moves files only inside the chosen folder, keeps extensions, never deletes
- sends identical files to `Duplicates`
- logs every old name next to the new one in `old names.txt`
- leaves a file that is open in another app where it is and says so (tell the user to close that app and run the sort again)
- writes `sort-report.html` (open it for the user: `open` on Mac, `start ""` on Windows)

## 6. Undo

If the user wants it back the way it was (this also works if a sort stopped halfway):

```
python3 "<skill>/scripts/undo.py" "<folder>"
```

## Reply to the user

Keep it short: how many files, the count per folder, anything that landed in `Other`, and that the report is open. Do not list every file.