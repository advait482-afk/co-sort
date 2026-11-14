# Changelog

All notable changes to this project are listed here. Versions follow [Semantic Versioning](https://semver.org).

## Unreleased

## 0.1.0 (2026-11-15)

First public release.

- `prep.py`: scans a folder without changing it; reads type, size, capture date and camera; finds exact duplicates by content hash; flags likely screenshots; pulls three frames per video; measures loudness; optional local transcript with faster-whisper; builds numbered contact sheets.
- `apply.py`: renames and moves files inside the chosen folder only, keeps extensions, sends duplicates to `Duplicates` and leftovers to `Other`, logs every old name in `old names.txt`, and writes `sort-report.html`. Supports `--dry-run`.
- `undo.py`: restores the last run, including runs that stopped halfway. Files still open in another app stay on the undo list until they can be moved.
- `SKILL.md` and `AGENTS.md`: step-by-step instructions for the agent, with default folders and naming rules.
- Setup scripts for macOS and Windows that install Python packages and ffmpeg.
- Windows handling for UTF-8 file names, reserved names such as `CON` and `NUL`, and files locked by another app. The Windows setup script skips the Microsoft Store "python" shortcut and reloads PATH after installing.
- Every move is written to a journal before it happens, so a power cut or crash can't lose track of a file.
- Smoke test (`tests/smoke_test.py`) and GitHub Actions on macOS, Windows and Linux.
