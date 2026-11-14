# Co&Co Sort setup for Windows 10 / 11. Safe to run more than once.
$ErrorActionPreference = "Continue"

# Windows only sees newly installed programs in a new window. Reload PATH
# from the registry so this window finds them straight away.
function Refresh-Path {
  $machine = [System.Environment]::GetEnvironmentVariable("Path", "Machine")
  $user = [System.Environment]::GetEnvironmentVariable("Path", "User")
  $env:Path = "$machine;$user"
}

# The "python" that ships with Windows is a shortcut that only opens the
# Microsoft Store. Treat it as missing.
function Find-Python {
  foreach ($name in @("python", "py")) {
    $cmd = Get-Command $name -ErrorAction SilentlyContinue
    if ($cmd -and $cmd.Source -notmatch "WindowsApps") {
      if ($name -eq "py") { return "py -3" }
      return "python"
    }
  }
  return $null
}

Write-Host "1/4 Checking Python"
$py = Find-Python
if (-not $py) {
  Write-Host "Installing Python 3.12"
  winget install -e --id Python.Python.3.12 --accept-source-agreements --accept-package-agreements
  Refresh-Path
  $py = Find-Python
}
if (-not $py) {
  Write-Host "Python could not be found after installing. Close this window, open a new one and run this script again."
  exit 1
}
Write-Host "Using: $py"

Write-Host "2/4 Checking ffmpeg"
if (-not (Get-Command ffmpeg -ErrorAction SilentlyContinue)) {
  winget install -e --id Gyan.FFmpeg --accept-source-agreements --accept-package-agreements
  Refresh-Path
}
if (-not (Get-Command ffmpeg -ErrorAction SilentlyContinue)) {
  Write-Host "ffmpeg was installed but this window can't see it yet. Close it, open a new one and run this script again."
}

Write-Host "3/4 Installing image tools"
Invoke-Expression "$py -m pip install --user --upgrade pillow pillow-heif"

Write-Host "4/4 Installing speech to text (optional, about 200 MB)"
Invoke-Expression "$py -m pip install --user --upgrade faster-whisper"
if ($LASTEXITCODE -ne 0) { Write-Host "Speech to text skipped. Sorting still works without it." }

Write-Host "Done. Co&Co Sort is ready. Say 'sort' to Claude."
