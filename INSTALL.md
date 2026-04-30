# Installation and Setup (Windows & Linux)

This guide covers final, tested steps to install and run the Discord Music Bot on both Linux (Debian/Ubuntu-like) and Windows (PowerShell). Installation is now simplified: FFmpeg is bundled as a Python package, so you only need Python and git.

---

## Quick summary
- **Linux**: `./install.sh` then optionally `sudo ./install.sh --systemd` to create a systemd service.
- **Windows**: `.\install.ps1 -Run` for quick testing, or `.\install.ps1` to set up with Task Scheduler.
- **Both**: Python 3.11+ is the only requirement. FFmpeg comes bundled with Python dependencies!

---

## Prerequisites (both OSes)
- **Python 3.11+** installed and on PATH (that's it!)
- A Discord application bot token (from Discord Developer Portal)
- Git (optional, for cloning; you can also download ZIP)

**Note:** FFmpeg and Opus are now bundled as Python packages (`imageio-ffmpeg` and `opuslib`), so no separate system installation is needed. The bot stores local cache under `./cache` for fast repeat playback.

---

## Files to know
- `index.py` — main bot launcher
- `requirements.txt` — Python dependencies (includes `imageio-ffmpeg`)
- `install.sh` — local installer for Linux (creates `venv` and installs Python deps)
- `install.ps1` — local installer for Windows (creates `venv` and installs Python deps)
- `INSTALL.md` — this guide
- `.env.example` — sample environment file (copy to `.env`)

---

## 1) Linux (Debian / Ubuntu / similar)

A. Install Python (only system dependency!)

```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-pip git
```

**Note:** FFmpeg and Opus are now bundled with Python dependencies, so you don't need to install them separately.

B. Extract / clone repo and run installer

If you downloaded a ZIP and extracted it into `/home/youruser/discord-music-bot`:

```bash
cd /home/youruser/discord-music-bot
# Quick one-command install + run
./install.sh --run
```

The script will create a `venv` in the repo, install `requirements.txt` (including `imageio-ffmpeg` and `opuslib`), and copy `.env.example` → `.env` if missing.

C. Edit `.env`

Open `.env` in an editor and set your `DISCORD_TOKEN` and optionally `SPOTIFY_CLIENT_ID`, `SPOTIFY_CLIENT_SECRET`, `GENIUS_ACCESS_TOKEN`, and other settings.

For restricted YouTube videos/playlists (age/region/private access via your account), add one of these:

```env
# Recommended: automatic browser cookie loading
YTDLP_COOKIES_FROM_BROWSER=edge
# Optional profile (leave blank for default)
YTDLP_COOKIES_BROWSER_PROFILE=

# Alternative: exported cookie file
YTDLP_COOKIEFILE=./cookies.txt
```

D. Test run (terminal) [optional]

```bash
source venv/bin/activate
python index.py
```

E. Make it persistent with systemd (optional, run as root)

```bash
sudo ./install.sh --systemd
sudo systemctl start discord-music-bot
sudo systemctl enable discord-music-bot
sudo journalctl -u discord-music-bot -f
```

The `--systemd` flag creates `/etc/systemd/system/discord-music-bot.service` for the user who invoked the script (via `SUDO_USER`) and sets it to restart on failure.

F. Logs and troubleshooting
- Tail logs: `sudo journalctl -u discord-music-bot -f` (if systemd), or `tail -f bot.log` if launching in terminal.
- Common errors: missing `DISCORD_TOKEN` in `.env`, missing Python dependencies (run `pip install -r requirements.txt` again).
- If FFmpeg or Opus can't be found: 
  - FFmpeg: `python -c "import imageio_ffmpeg; print(imageio_ffmpeg.get_ffmpeg_exe())"`
  - Opus: `python -c "import opuslib; print(opuslib.__file__)"`

G. 24/7 operation and monitoring
- A plain terminal session stops when the terminal closes, so use `systemd` for true 24/7 Linux hosting.
- Recommended monitoring commands:

```bash
sudo systemctl status discord-music-bot
sudo journalctl -u discord-music-bot -f
tail -f logs/bot.log
```

- The bot writes logs to `logs/bot.log` and keeps 7 days of history automatically.
- If you use the one-command installer with `--systemd`, the bot will also restart on reboot and after crashes.

---

## 2) Windows (PowerShell)

A. Install Python (only requirement!)
- Install Python 3.11+ from [python.org](https://python.org) (ensure `Add Python to PATH` is checked).
- **FFmpeg and Opus are now bundled as Python packages, so no separate installation needed!**

B. Create repo folder and extract
- Extract the ZIP to `C:\Users\YourUser\discord-music-bot` or clone the repo with Git.

C. Quick one-command install + run (recommended for testing)

```powershell
cd C:\Users\YourUser\discord-music-bot
PowerShell -ExecutionPolicy Bypass -File install.ps1 -Run
```

Or step-by-step:

```powershell
cd C:\Users\YourUser\discord-music-bot
python -m venv venv
# Activate
venv\Scripts\Activate.ps1
# Upgrade pip and install deps (including imageio-ffmpeg and opuslib)
python -m pip install --upgrade pip
pip install -r requirements.txt
```

D. Prepare `.env`

```powershell
copy .env.example .env
# Edit .env in Notepad or VS Code
notepad .env
```

For restricted YouTube videos/playlists, configure one of these in `.env`:

```env
# Recommended: automatic browser cookie loading
YTDLP_COOKIES_FROM_BROWSER=edge
YTDLP_COOKIES_BROWSER_PROFILE=

# Alternative: exported cookie file
YTDLP_COOKIEFILE=./cookies.txt
```

E. Run the bot (PowerShell)

```powershell
venv\Scripts\Activate.ps1
python index.py
```

F. Run automatically on Windows startup (two options)

1) **Task Scheduler (simple)**: Create a task that runs on user login and starts: `C:\path\to\venv\Scripts\python.exe C:\path\to\index.py`.

2) **NSSM (recommended for services)**: Install NSSM (Non-Sucking Service Manager) and create a Windows service to run the Python executable with `index.py` as the argument.

G. 24/7 operation and monitoring
- A normal terminal session stops when the terminal closes, so use Task Scheduler or NSSM for 24/7 Windows hosting.
- Recommended monitoring commands:

```powershell
schtasks /Query /TN DiscordMusicBot
Get-Content .\logs\bot.log -Wait
```

- The bot writes logs to `logs/bot.log` and keeps 7 days of history automatically.
- If you use `install.ps1 -CreateTask`, the bot can start at logon and survive terminal closure.
 
You can also create a Scheduled Task from PowerShell using the installer:

```powershell
# Create a Scheduled Task that runs at logon
PowerShell -ExecutionPolicy Bypass -File install.ps1 -CreateTask
```

---

## 3) One-command / zip distribution flow (recommended for simple installs)
1. Create a ZIP of the repository (exclude `.git`, `venv`, and large caches) and upload it for users.
2. User downloads the ZIP and extracts into a folder.
3. On Linux: `cd repo && ./install.sh` — this sets up the `venv` and dependencies.
4. On Windows: `cd repo && python -m venv venv && venv\Scripts\Activate.ps1 && pip install -r requirements.txt` — or provide a short PowerShell script `install.ps1` with the same steps.

Yes — after extracting and running `install.sh` (Linux) or running the short Windows install steps, the user will only need to edit `.env` then run `python index.py` to start the bot.

---

## 5) Helpful commands
- Activate venv (Linux): `source venv/bin/activate`
- Activate venv (Windows PowerShell): `venv\Scripts\Activate.ps1`
- Run tests: `python -m pytest -q`
- Check ffmpeg on PATH: `ffmpeg -version`
- Run the bot `python index.py`
---