# Installation and Setup (Windows & Linux)

This guide covers final, tested steps to install and run the Discord Music Bot on both Linux (Debian/Ubuntu-like) and Windows (PowerShell). It includes system dependencies, Python virtual environment setup, environment variables, quick run, and recommended persistent service setup (systemd on Linux, Task Scheduler or NSSM on Windows).

---

## Quick summary
- Linux: recommended method — unzip, run `./install.sh` then optionally `sudo ./install.sh --systemd` to create a systemd service.
- Windows: create a `venv`, activate it, `pip install -r requirements.txt`, edit `.env`, then run `python index.py`. For persistence, use Task Scheduler or NSSM.

---

## Prerequisites (both OSes)
- Python 3.11+ installed and on PATH
- A Discord application bot token (from Discord Developer Portal)
- `ffmpeg` installed on host (required for audio)
- `libopus` or equivalent installed (Linux package names vary; Windows ffmpeg builds include opus)

Note: The bot stores local cache under `./cache`. The repository includes an `install.sh` for Linux to create a venv and install Python deps.

---

## Files to know
- `index.py` — main bot launcher
- `requirements.txt` — Python dependencies
- `install.sh` — local installer for Linux (creates `venv` and installs Python deps)
- `INSTALL.md` — this guide
- `.env.example` — sample environment file (copy to `.env`)

---

## 1) Linux (Debian / Ubuntu / similar)

A. Install system dependencies

```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-pip ffmpeg libopus-dev git
```

B. Extract / clone repo and run installer

If you downloaded a ZIP and extracted it into `/home/youruser/discord-music-bot`:

```bash
cd /home/youruser/discord-music-bot
# Quick one-command install + run
./install.sh --run
```

The script will create a `venv` in the repo, install `requirements.txt`, and copy `.env.example` → `.env` if missing.

C. Edit `.env`

Open `.env` in an editor and set your `DISCORD_TOKEN` and optionally `SPOTIFY_CLIENT_ID`, `SPOTIFY_CLIENT_SECRET`, `GENIUS_ACCESS_TOKEN`, and other settings.

D. Test run (terminal)

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
- Common errors: missing `ffmpeg` (install via apt), missing `DISCORD_TOKEN` in `.env`, missing Python dependencies (`pip install -r requirements.txt`).

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

A. Install system dependencies
- Install Python 3.11+ from python.org (ensure `Add Python to PATH` is checked).
- Install `ffmpeg`:
  - Option 1 (recommended): Download a static build of ffmpeg and add its `bin` directory to PATH.
  - Option 2: Install via package managers (choco) `choco install ffmpeg`.

B. Create repo folder and extract
- Extract the ZIP to `C:\Users\YourUser\discord-music-bot` or clone the repo with Git.

C. Create and activate virtual environment (PowerShell)

```powershell
cd C:\Users\YourUser\discord-music-bot
# Quick one-command install + run (recommended for testing)
PowerShell -ExecutionPolicy Bypass -File install.ps1 -Run

# Or step-by-step:
python -m venv venv
# Activate
venv\Scripts\Activate.ps1
# Upgrade pip and install deps
python -m pip install --upgrade pip
pip install -r requirements.txt
```

D. Prepare `.env`

```powershell
copy .env.example .env
# Edit .env in Notepad or VS Code
notepad .env
```

E. Run the bot (PowerShell)

```powershell
venv\Scripts\Activate.ps1
python index.py
```

F. Run automatically on Windows startup (two options)

1) Task Scheduler (simple): create a task that runs on user login and starts: `C:\path\to\venv\Scripts\python.exe C:\path\to\index.py`.

2) NSSM (recommended for services): install NSSM (Non-Sucking Service Manager) and create a Windows service to run the Python executable with `index.py` as the argument.

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