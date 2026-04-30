# Setup & Quick Start Guide

## 🚀 Quick Setup (2 minutes)

### 1. Prerequisites Check
```bash
python --version  # Should be 3.11+
```

**That's it!** FFmpeg is now bundled as a Python package (`imageio-ffmpeg`), so no system dependencies are needed.

### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

### 3. Configure Bot
```bash
# Copy .env template
cp .env.example .env

# Edit .env and add your credentials
# Required: DISCORD_TOKEN
# Optional: Spotify & Genius tokens (for advanced features)
```

### 4. Run the Bot
```bash
python index.py
```

## 📋 Environment Variables

**Required:**
- `DISCORD_TOKEN` - Your Discord bot token from [Discord Developer Portal](https://discord.com/developers/applications)

**Optional (for advanced features):**
- `SPOTIFY_CLIENT_ID` - Spotify API credentials
- `SPOTIFY_CLIENT_SECRET` - Spotify API secret
- `GENIUS_ACCESS_TOKEN` - Genius API token for lyrics

**Settings:**
- `DEFAULT_VOLUME=50` - Default playback volume (0-100)
- `DEFAULT_LANGUAGE=en` - Default language (en, es, fr)
- `VOICE_TIMEOUT=300` - Seconds before auto-disconnect
- `IDLE_DISCONNECT_TIME=600` - Idle timeout

## 🧪 Running Tests

```bash
# Run all tests
pytest tests/ -v --asyncio-mode=auto

# Run specific test file
pytest tests/test_queue.py -v --asyncio-mode=auto

# Run with coverage
pytest tests/ --cov=src
```

## 📁 Project Structure

```
src/
├── __init__.py           # Module exports
├── player.py             # MusicPlayer & GuildPlayer classes
├── queue.py              # Queue & Track classes (tested ✅)
├── providers.py          # YouTube & Spotify providers
├── embeds.py             # Discord embed generation
├── lyrics.py             # Lyrics fetching service
└── cache.py              # Local audio caching

commands/
├── __init__.py
├── play.py               # /play command
├── playback.py           # /pause, /resume, /stop, /skip, /previous
├── queue.py              # Queue management commands
├── audio.py              # /volume, /seek, /lyrics
└── utility.py            # /np, /join, /leave, /help, /ping

events/
└── __init__.py           # Button handlers & voice events

tests/
├── conftest.py           # Pytest configuration & fixtures
└── test_queue.py         # Queue module tests (7 tests ✅)

index.py                 # Bot main entry point
config.py                # Configuration & localization
requirements.txt         # Python dependencies
.env.example             # Environment template
LICENSE                  # MIT License
```

## 🎯 Getting Your Discord Bot Token

1. Go to [Discord Developer Portal](https://discord.com/developers/applications)
2. Click "New Application"
3. Go to "Bot" section → "Add Bot"
4. Copy the token under "TOKEN"
5. Set it in `.env`: `DISCORD_TOKEN=your_token_here`

Note: Keep this token **secret**! Never share it.

## 🎶 Getting Spotify Credentials (Optional)

1. Go to [Spotify Developer Dashboard](https://developer.spotify.com)
2. Create an application
3. Copy Client ID and Client Secret
4. Add to `.env`:
   ```env
   SPOTIFY_CLIENT_ID=your_id
   SPOTIFY_CLIENT_SECRET=your_secret
   ```

## 📜 Getting Genius Token (Optional)

1. Go to [Genius API](https://genius.com/api-clients)
2. Get your access token
3. Add to `.env`:
   ```env
   GENIUS_ACCESS_TOKEN=your_token
   ```

## ⚙️ Bot Permissions

Invite link format:
```
https://discord.com/api/oauth2/authorize?client_id=YOUR_BOT_ID&scope=bot&permissions=274877906960
```

Required permissions:
- ✅ Send Messages
- ✅ Embed Links
- ✅ Connect (Voice)
- ✅ Speak (Voice)
- ✅ Use Slash Commands

## 🛠️ Troubleshooting

### Bot won't start
```
Error: DISCORD_TOKEN environment variable not set
Fix: Add DISCORD_TOKEN to .env
```

### No audio output
```
1. Ensure bot is in voice channel: /join
2. Check Discord allows bot to speak
3. Verify YouTube/Spotify are accessible
```

### Lyrics not loading
```
1. Add GENIUS_ACCESS_TOKEN to .env (optional)
2. LRCLIB is used as fallback
3. Not all songs have lyrics
```

### Tests failing
```bash
# Run with proper asyncio mode
pytest tests/ -v --asyncio-mode=auto
```

## 📊 Test Results

```
tests/test_queue.py::test_add_track ✅ PASSED
tests/test_queue.py::test_remove_track ✅ PASSED
tests/test_queue.py::test_clear_queue ✅ PASSED
tests/test_queue.py::test_shuffle_queue ✅ PASSED
tests/test_queue.py::test_move_track ✅ PASSED
tests/test_queue.py::test_toggle_loop ✅ PASSED
tests/test_queue.py::test_queue_info ✅ PASSED

7 passed in 0.09s ✅
```

## 🚀 Advanced Usage

### Custom Commands
Add new commands in `commands/` directory:
```python
@discord.app_commands.command(name="mycommand")
async def my_command(interaction: discord.Interaction):
    pass
```

Then register in `index.py` MusicBot cog.

### Custom Localization
Add language in `LOCALIZATION` dict in `config.py`:
```python
"de": {  # German
    "now_playing": "Wird gerade abgespielt",
    # ... more translations
},
```

### Extend Queue Features
Add methods to `Queue` class in `src/queue.py`:
```python
async def special_feature(self):
    """Your custom feature"""
    pass
```

## 📞 Support

- **Issues**: Check error logs in console
- **Privacy**: See [PRIVACY_POLICY.md](../PRIVACY_POLICY.md)
- **Terms**: See [TERMS_OF_SERVICE.md](../TERMS_OF_SERVICE.md)

---

✨ Happy music streaming!
