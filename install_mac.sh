#!/usr/bin/env bash
# Co&Co Sort setup for Mac (Apple chip or Intel). Safe to run more than once.
set -e

echo "1/4 Checking Homebrew"
if ! command -v brew >/dev/null 2>&1; then
  echo "Installing Homebrew (it may ask for your Mac password once)"
  /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
  eval "$(/opt/homebrew/bin/brew shellenv 2>/dev/null || /usr/local/bin/brew shellenv)"
fi

echo "2/4 Installing ffmpeg and Python"
command -v ffmpeg >/dev/null 2>&1 || brew install ffmpeg
command -v python3 >/dev/null 2>&1 || brew install python

echo "3/4 Installing image tools"
python3 -m pip install --user --upgrade pillow pillow-heif 2>/dev/null \
  || python3 -m pip install --user --break-system-packages --upgrade pillow pillow-heif

echo "4/4 Installing speech to text (optional, about 200 MB)"
python3 -m pip install --user --upgrade faster-whisper 2>/dev/null \
  || python3 -m pip install --user --break-system-packages --upgrade faster-whisper \
  || echo "Speech to text skipped. Sorting still works without it."

echo "Done. Co&Co Sort is ready."
