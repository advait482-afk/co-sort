# Instructions for AI agents

This repository is a footage-sorting skill. When the user asks you to sort a folder of media, follow `SKILL.md` in this folder step by step.

You need to be able to:

- run shell commands (`python3 scripts/prep.py`, `scripts/apply.py`, `scripts/undo.py`)
- open and look at image files (the contact sheets in `<folder>/.cosort/sheets/`)
- write a JSON file (`<folder>/.cosort/plan.json`)

Rules that always apply:

- Never delete, overwrite or edit the contents of a user's media file.
- Only move files inside the folder the user chose.
- Run `apply.py --dry-run` and show the counts before the real run, unless the user has already said to go ahead.

## Working on this repository

If you are changing the code rather than sorting footage, run the smoke test before and after your change:

```
python3 tests/smoke_test.py
```

It needs ffmpeg and Pillow, creates a temporary fake shoot, and checks that prep, apply and undo round-trip without losing a file.
