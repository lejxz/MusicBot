# Installation and Setup (Windows & Linux)

This guide covers final, tested steps to install and run the Discord Music Bot on both Linux (Debian/Ubuntu-like) and Windows (PowerShell).

---

## ⚠️ CRITICAL: FFmpeg Requirement on Linux

**Linux users SHOULD use system FFmpeg.** The bundled `imageio-ffmpeg` was observed to fail on Ubuntu 24.04 (GLIBC 2.39) with **FFmpeg exit code -11 (SIGSEGV)**, causing audio playback to fail.

**Install on Linux:**
- Debian/Ubuntu runtime: `sudo apt update && sudo apt install -y ffmpeg libopus0`
- Fedora runtime: `sudo dnf install -y ffmpeg-free opus`
- RHEL/Rocky/Alma runtime: enable a repository providing `ffmpeg-free`, then install and capability-test it.

**Windows**: System FFmpeg is preferred when configured; validated `imageio-ffmpeg` fallback is supported.
**macOS**: Install FFmpeg and Opus with Homebrew as shown in the macOS section.

---

## Quick summary
- **Linux**: `./install.sh` (checks for system FFmpeg), then `sudo ./install.sh --systemd` for persistent service.
- **Windows**: `.\install.ps1 -Run` for quick testing, or `.\install.ps1` to set up with Task Scheduler.
- **Python**: 3.11+ required on all platforms.
- **Python audio packages**: `imageio-ffmpeg` supplies an FFmpeg fallback;
- `requirements.txt` — Python dependencies
- `install.sh` — Linux installer (creates `venv`, checks for system FFmpeg)
- `install.ps1` — Windows installer (creates `venv`)
- `INSTALL.md` — this guide
- `.env.example` — sample environment file

---

## 1) Linux (Debian / Ubuntu / similar)

### A. Install system dependencies

```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-pip git ffmpeg libopus0
```

**Verify installation:**
```bash
ffmpeg -version
ldconfig -p | grep libopus
```

### B. Clone/extract and run installer

```bash
cd /path/to/discord-music-bot
./install.sh --run
```

The script will:
1. ✅ Check for system FFmpeg and Opus
2. Create a `venv` in the repo
3. Install `requirements.txt` dependencies
4. Copy `.env.example` → `.env` if missing

If FFmpeg/Opus is not found, the installer will **fail with clear instructions** on how to install them.

### C. Edit `.env`

Open `.env` and set your credentials:
```env
DISCORD_TOKEN=your_token_here
# Optional:
SPOTIFY_CLIENT_ID=...
SPOTIFY_CLIENT_SECRET=...
GENIUS_ACCESS_TOKEN=...
```

For restricted YouTube videos/playlists:
```env
YTDLP_COOKIES_FROM_BROWSER=edge
```

### D. Test run

```bash
source venv/bin/activate
python index.py
```

Press `Ctrl+C` to stop.

### E. Make it persistent with systemd or PM2 (recommended for 24/7)

#### Option 1: systemd (System-level service, requires root)

```bash
sudo ./install.sh --systemd
sudo systemctl start discord-music-bot
sudo systemctl enable discord-music-bot
```

**View logs:**
```bash
sudo journalctl -u discord-music-bot -f
```

**Restart / Stop / Status:**
```bash
sudo systemctl restart discord-music-bot
sudo systemctl stop discord-music-bot
sudo systemctl status discord-music-bot
```

#### Option 2: PM2 (User-level process manager, no root required)

If PM2 is installed on your system (`npm install -g pm2`), you can manage the bot without requiring root or sudo privileges:

```bash
# Start the bot using PM2 with the virtualenv Python interpreter:
pm2 start /path/to/MusicBot/venv/bin/python --name musicbot -- /path/to/MusicBot/index.py

# View status and live logs:
pm2 status
pm2 logs musicbot

# Restart or stop:
pm2 restart musicbot
pm2 stop musicbot

# Save PM2 process list to persist across server reboots:
pm2 save
```

### F. Troubleshooting on Linux

**Audio not playing / FFmpeg exit code -11?**
- System FFmpeg installed? `ffmpeg -version`
- Bundled imageio-ffmpeg fallback was observed to fail on Ubuntu 24.04. Use system FFmpeg.
- Fix: `sudo apt install ffmpeg libopus0`

**FFmpeg or Opus not found?**
```bash
# Check system FFmpeg:
which ffmpeg

# Check Opus library:
ldconfig -p | grep libopus
```

**"FFmpeg is required" error at startup?**
- Reinstall system packages: `sudo apt install ffmpeg libopus0`

**Logs and monitoring:**
```bash
# View live logs
sudo journalctl -u discord-music-bot -f

# View bot application logs
tail -f logs/bot.log

# Check service status
sudo systemctl status discord-music-bot

# View recent errors
sudo journalctl -u discord-music-bot -n 50 --no-pager
```

---

## 2) Windows (PowerShell)

### A. Install Python

Install Python 3.11+ from [python.org](https://python.org). **Ensure "Add Python to PATH" is checked during installation.**

The Python requirements provide a bundled FFmpeg fallback, so a separate
FFmpeg installation is normally unnecessary on Windows.

**Verify:**
```powershell
python --version
```

### B. Extract and run installer

```powershell
cd C:\Users\YourUser\discord-music-bot
PowerShell -ExecutionPolicy Bypass -File install.ps1 -Run
```

Or step-by-step:
```powershell
cd C:\Users\YourUser\discord-music-bot
python -m venv venv
venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

### C. Edit `.env`

```powershell
copy .env.example .env
notepad .env
```

Add your Discord token and optional Spotify/Genius credentials.

### D. Run the bot

```powershell
venv\Scripts\Activate.ps1
python index.py
```

Press `Ctrl+C` to stop.

### E. Run on Windows startup (optional)

#### Option 1: Task Scheduler (simple)

1. Open Task Scheduler (`taskschd.msc`)
2. Create Basic Task → "Discord Music Bot"
3. Trigger: "At log on"
4. Action: Start program
5. Program: `C:\path\to\venv\Scripts\python.exe`
6. Arguments: `C:\path\to\index.py`
7. Check "Run with highest privileges"

#### Option 2: NSSM (recommended for services)

Install [NSSM](https://nssm.cc/download):
```powershell
nssm install DiscordMusicBot C:\path\to\venv\Scripts\python.exe "C:\path\to\index.py"
nssm start DiscordMusicBot
```

### F. Troubleshooting on Windows

**Python not found?**
- Reinstall Python, checking "Add Python to PATH"
- Verify: `python --version`

**Permission denied running .ps1?**
```powershell
PowerShell -ExecutionPolicy Bypass -File install.ps1
```

**View logs:**
```powershell
Get-Content .\logs\bot.log -Wait
```

---

## 3) Docker (Linux, easiest option for 24/7 deployment)

**Recommended for 24/7 Linux hosting.** Docker automatically handles FFmpeg/Opus, reducing setup complexity.

### A. Prerequisites

- Docker and Docker Compose installed
  - Ubuntu/Debian: `sudo apt install docker.io docker-compose-plugin`
  - Verify: `docker --version` and `docker compose version`

### B. Quick start

```bash
cd /path/to/discord-music-bot
cp .env.example .env
# Edit .env with your DISCORD_TOKEN
nano .env

# Build and start
docker compose up -d

# View logs
docker compose logs -f
```

That's it! The bot runs in the background with automatic restart on failure.

### C. Common Docker commands

```bash
# View logs
docker compose logs -f discord-music-bot

# Stop the bot
docker compose stop

# Start the bot
docker compose start

# Restart the bot
docker compose restart

# Remove everything (wipe cache/logs)
docker compose down -v

# Check status
docker compose ps
```

### D. Persist data (cache, logs) outside container

The `docker-compose.yml` already mounts:
- `./cache` → `/app/cache` (audio cache)
- `./logs` → `/app/logs` (bot logs)

These persist even if the container is removed:

```bash
# View bot logs on host
tail -f logs/bot.log

# Check cache size
du -sh cache/
```

### E. Auto-start on system boot

```bash
# Enable Docker to start on boot
sudo systemctl enable docker

# Make compose auto-restart
# (already set in docker-compose.yml: restart: unless-stopped)

# Start bot on boot
cd /path/to/discord-music-bot
docker compose up -d
```

### F. Troubleshooting Docker

**Permission denied error?**
```bash
# Run Docker without sudo (optional)
sudo usermod -aG docker $USER
newgrp docker
```

**Build image locally:**
```bash
docker compose build --no-cache
```

**Inspect running container:**
```bash
docker compose exec discord-music-bot bash
# Inside container: ffmpeg -version
```

**Clear all Docker data:**
```bash
docker compose down -v
docker system prune -a
```

---

## 4) macOS

### A. Install system dependencies

```bash
brew install python@3.12 ffmpeg opus
```

### B. Clone and install

```bash
cd /path/to/discord-music-bot
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### C. Edit `.env` and run

```bash
cp .env.example .env
# Edit .env with your token
python index.py
```

### D. Keep running 24/7 with launchd

Create `~/Library/LaunchAgents/com.discord-music-bot.plist`:
```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.discord-music-bot</string>
    <key>Program</key>
    <string>/path/to/venv/bin/python</string>
    <key>ProgramArguments</key>
    <array>
        <string>/path/to/index.py</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
</dict>
</plist>
```

Then:
```bash
launchctl load ~/Library/LaunchAgents/com.discord-music-bot.plist
launchctl start com.discord-music-bot
```

---

## 5) Common Issues

### Audio stops after first track / "No track is currently playing"

**Cause**: FFmpeg crash (exit code -11 on Linux).

**Fix on Linux**:
```bash
sudo apt install ffmpeg libopus0
```

**Fix on Windows/macOS**: Reinstall FFmpeg via Homebrew or direct download.

### "FFmpeg is required for voice playback but was not found"

**Linux**:
```bash
sudo apt install ffmpeg
```

**Windows**: Ensure Python is on PATH and FFmpeg is in the bundled package.

**macOS**:
```bash
brew install ffmpeg
```

### Bot crashes with "exit code -11"

On Ubuntu 24.04, the bundled imageio-ffmpeg fallback was observed to exit with code -11 (SIGSEGV).

**Linux fix:**
Install system FFmpeg:
```bash
sudo apt install ffmpeg libopus0
```

### Slash commands not appearing in Discord

1. Bot must be in the server with `/applications.commands` scope
2. Ensure bot has "Use Slash Commands" permission
3. Restart the Discord client (`Ctrl+R`)
4. Check bot logs: `journalctl -u discord-music-bot -f` (Linux) or `Get-Content .\logs\bot.log` (Windows)

---

## 6) Helpful commands

**Check system FFmpeg/Opus (Linux):**
```bash
ffmpeg -version
ldconfig -p | grep libopus
```

**View bot logs:**
```bash
# Linux (systemd)
sudo journalctl -u discord-music-bot -f

# PM2
pm2 logs musicbot

# Linux (terminal)
tail -f logs/bot.log

---

## 7) Testing

Run the full test suite:
```bash
python -m pytest tests/ -v --asyncio-mode=auto
```

Run a focused test file:
```bash
python -m pytest tests/test_queue.py -v --asyncio-mode=auto
```

Run with coverage:
```bash
python -m pytest tests/ --cov=src
```

---

## 8) Project Structure

```text
commands/          Slash command handlers
events/            Event handlers and UI buttons
src/               Core services (player, queue, providers, cache, embeds)
tests/             Unit tests and integration checks
index.py           Main bot entry point
config.py          Environment configuration and localization
install.sh         Linux installer
install.ps1        Windows installer
INSTALL.md         Full setup and usage guide
requirements.txt   Python dependencies
.env.example       Example environment file
```

---

## 9) Advanced Usage

### Custom Commands
Add new commands in the `commands/` directory:
```python
@discord.app_commands.command(name="mycommand")
async def my_command(interaction: discord.Interaction):
  pass
```

Register the command in `index.py` so the bot loads it on startup.

### Custom Localization
Add a new language in the `LOCALIZATION` dictionary in `config.py`:
```python
"de": {  # German
  "now_playing": "Wird gerade abgespielt",
  # ... more translations
},
```

### Extend Queue Features
Add new queue behavior in `src/queue.py`:
```python
async def special_feature(self):
  """Your custom feature"""
  pass
```

Get-Content .\logs\bot.log -Wait
```

**Restart bot:**
```bash
# Linux systemd
sudo systemctl restart discord-music-bot

# PM2
pm2 restart musicbot
```

**Stop bot:**
```bash
# Linux systemd
sudo systemctl stop discord-music-bot

# PM2
pm2 stop musicbot

# Any: Ctrl+C in terminal
```

**Run tests:**
```bash
source venv/bin/activate  # Linux/macOS
python -m pytest tests/ -v
```

---

## 7) Support

- **Issue**: Check `logs/bot.log` for error messages
- **FFmpeg problems on Linux**: Verify system installation with `ffmpeg -version`
- **Discord token issues**: Ensure token is valid at [Discord Developer Portal](https://discord.com/developers/applications)

---

✨ **Happy music streaming!**
