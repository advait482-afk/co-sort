# Co Sort

[![Smoke test](https://github.com/advait482-afk/co-sort/actions/workflows/smoke-test.yml/badge.svg)](https://github.com/advait482-afk/co-sort/actions/workflows/smoke-test.yml)

**Turn a folder of `IMG_4821.MOV` files into named files in sensible folders.**

Co Sort is an open-source skill for AI agents (Claude Code, the Claude desktop app, and any agent that follows `SKILL.md` or `AGENTS.md`). Drop a whole shoot into one folder, say **"sort"**, and the agent looks at every video, photo and audio file, gives each one a descriptive name, and moves it into folders.

- Runs on your own computer. Your footage is never uploaded.
- Never deletes a file. Every move is logged and can be undone with one command.
- Works on macOS and Windows.

```
Before                                After
Sort me/                              Sort me/
  IMG_4821.MOV                          Talking head/
  IMG_4822.MOV                            2026-10-12 intro about the retreat.mov
  IMG_4823.HEIC              ->         B-roll/
  IMG_4824.MOV                            2026-10-12 garden walkway slow pan.mov
  Screenshot 2026-10-12.png             Photos/
  IMG_4821 copy.MOV                       2026-10-12 cafe latte art closeup.heic
                                        Screenshots/
                                          2026-10-12 booking confirmation screen.png
                                        Duplicates/
                                          IMG_4821 copy.MOV
                                        old names.txt
                                        sort-report.html
```

## Why

Editors, content teams and creators lose hours renaming phone and camera dumps before they can start cutting. Filenames like `IMG_4821.MOV` say nothing about what is in the clip. Co Sort does the first pass for you: it watches, listens, names and files, and leaves you a visual report to check.

## How it works

1. **Prep** (`scripts/prep.py`) scans the folder without changing anything. It reads file types, capture dates and camera info, finds exact duplicates by content hash, pulls three frames from each video, measures loudness, and optionally transcribes the first seconds of speech on your machine. It then builds numbered contact sheets so the agent can look at many files cheaply.
2. **Decide.** The agent reads the contact sheets and the manifest and writes `plan.json`: a folder and a descriptive name for every file.
3. **Apply** (`scripts/apply.py`) renames and moves files inside the chosen folder only, sends identical files to `Duplicates`, logs every old name next to its new one in `old names.txt`, and writes `sort-report.html`. Run it with `--dry-run` first to see the counts.
4. **Undo** (`scripts/undo.py`) puts everything back the way it was.

## Requirements

- Python 3.9 or newer, with Pillow
- ffmpeg and ffprobe on your PATH
- Optional: [faster-whisper](https://github.com/SYSTRAN/faster-whisper) for local speech to text. Without it, talking head and b-roll are told apart by loudness and by what is in the frame.

The setup scripts install all of this for you:

- macOS: `bash setup/install_mac.sh`
- Windows: `powershell -ExecutionPolicy Bypass -File setup\install_windows.ps1`

## Install

Download this repository (green **Code** button, then **Download ZIP**, or grab the zip from the latest release).

- **Claude Code:** copy the folder to `~/.claude/skills/co-sort`.
- **Claude desktop app:** zip the folder and add it under Settings, Capabilities, Skills. Then give Claude access to the folder you want sorted.
- **Other agents:** point the agent at `AGENTS.md`. It needs to run shell commands and look at images.

## Use

1. Make a folder called `Sort me` on your Desktop and drop the shoot into it.
2. Open your agent and say **sort**.
3. Pick the folders: say **default** for Talking head, Voiceover, B-roll, Photos, Screenshots, Music and Sounds, or name your own, like "day 1, day 2, day 3" or "morning, cafe, outfit".
4. Check the dry run, approve, and open `sort-report.html`.

Changed your mind? Say **undo**, or run:

```
python3 scripts/undo.py "/path/to/Sort me"
```

On Windows, use `python` instead of `python3`.

## Naming

Files are named `YYYY-MM-DD what is in it`, using the capture date and three to seven plain words. Talking-head clips are named after what is said. Similar clips get ` 2`, ` 3` added automatically, and the original file extension is always kept.

## Privacy

Your files stay on your computer. Prep, transcription, renaming and the report all run locally. The only thing that leaves your machine is what your AI agent itself reads, which is the small contact-sheet images and the manifest text. Those go to whichever AI model you have chosen to use, under that provider's terms.

## Settings

- `COSORT_WHISPER=small` uses a larger speech model for better transcripts. The default is `base`.
- Tile size and files per contact sheet are constants at the top of `scripts/prep.py`.

## Status and roadmap

Version 0.1.0 is the first public release, and it has already been used on real client shoots. Windows support is in place (UTF-8 file names, reserved names, locked files) but has had less real-world use than macOS, so reports from Windows users are very welcome.

Planned next:

- Live progress view while a large folder is being sorted
- Better speech detection for Indian languages
- Tested Linux support
- Sorting by scene or location for multi-day shoots

See the [issues](https://github.com/advait482-afk/co-sort/issues) to suggest something or pick up a task.

## Testing

`tests/smoke_test.py` builds a small fake shoot (including a Kannada file name and an exact duplicate) and checks that prep, apply and undo never lose a file. It also fakes a file that is open in another app and a sort that stops halfway, and checks that undo still restores everything. It runs automatically on macOS, Windows and Linux for every change.

## Contributing

Bug reports, ideas and pull requests are welcome. Please read [CONTRIBUTING.md](CONTRIBUTING.md) first.

## Licence

[MIT](LICENSE). Made by [Co&Co](https://coandco.in), a creative agency in Bangalore.
