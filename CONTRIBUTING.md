# Contributing to Co&Co Sort

Thanks for helping. This project is small, so every bug report and pull request matters.

## Reporting a bug

Open an issue with the **Bug report** template. The most useful reports include:

- your operating system (macOS or Windows, and version)
- the agent you used (Claude Code, Claude desktop app, or another)
- what kind of files were in the folder (for example "iPhone HEIC photos and 4K MOV clips")
- the exact error message, or a screenshot of `sort-report.html`

Please don't attach private footage. A description of the file types is enough, and a tiny sample made up for the purpose is even better.

## Suggesting a feature

Open an issue with the **Feature request** template and describe the shoot or workflow that made you want it.

## Making a change

1. Fork the repository and create a branch.
2. Make your change. Keep the scripts dependency-light: the standard library, Pillow and ffmpeg, with anything else optional.
3. Run the smoke test:

   ```
   python3 tests/smoke_test.py
   ```

4. If you changed how sorting works, update `SKILL.md` and `README.md` to match.
5. Add a line under "Unreleased" in `CHANGELOG.md`.
6. Open a pull request and fill in the template.

## Ground rules for the code

These protect people's footage, so pull requests that break them won't be merged:

- Never delete a user's file or change what is inside it.
- Never move anything outside the folder being sorted.
- Every move must be logged before it happens, so undo still works after a crash.
- File names must survive non-English characters on both macOS and Windows.

## Releases

Maintainers tag releases as `vMAJOR.MINOR.PATCH` and write release notes from `CHANGELOG.md`.

## Conduct

Be kind and assume good intent. Harassment or personal attacks in issues, pull requests or discussions will be removed, and repeat offenders will be blocked.
