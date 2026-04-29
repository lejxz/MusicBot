# Discord Music Bot

A slash-command Discord music bot with YouTube and Spotify support, queue management, playback controls, lyrics, caching, and clean embeds.

## Features

### Playback
- `/play <song or URL>` - Play from YouTube, Spotify, or search query
- `/pause` - Pause current playback
- `/resume` - Resume playback
- `/stop` - Stop playback and clear the queue
- `/skip` - Skip the current track
- `/previous` - Play the previous track

### Queue
- `/queue` - Show the current queue
- `/remove <position>` - Remove a track from the queue
- `/clear` - Clear the queue
- `/shuffle` - Shuffle the queue
- `/loop` - Toggle loop mode
- `/move <from> <to>` - Reorder tracks

### Audio and Info
- `/volume <level>` - Set playback volume
- `/seek <time>` - Jump to a timestamp in the track
- `/lyrics <song>` - Fetch lyrics for the current or a specified track
- `/np` - Show the current now playing track
- `/join` - Join your voice channel
- `/leave` - Leave the voice channel
- `/help` - Show command help
- `/ping` - Check bot latency

## Highlights

- Multi-source playback with YouTube and Spotify
- Spotify playlists and albums are supported
- Local audio caching for faster repeat playback
- Automatic cache cleanup on startup
- Rotating logs stored in `logs/` with 7-day retention
- Clean, consistent embeds
- Deafens itself by default when joining voice
- Fully slash-command based, no prefix commands

## Installation

See [INSTALL.md](INSTALL.md) for full Windows and Linux setup instructions.

Quick start on Linux:
```bash
./install.sh --run
```

Quick start on Windows PowerShell:
```powershell
PowerShell -ExecutionPolicy Bypass -File install.ps1 -Run
```

## Configuration

Create a `.env` file from `.env.example` and fill in your values.

Required:
- `DISCORD_TOKEN`

Optional:
- `SPOTIFY_CLIENT_ID`
- `SPOTIFY_CLIENT_SECRET`
- `GENIUS_ACCESS_TOKEN`
- `YOUTUBE_API_KEY`

## Running

Start the bot:
```bash
python index.py
```

Run tests:
```bash
python -m pytest -q
```

## Project Structure

```text
commands/        Slash command handlers
events/          Event handlers and UI buttons
src/             Core services (player, queue, providers, cache, embeds)
tests/           Unit tests
index.py         Main bot entry point
config.py        Environment configuration
install.sh       Linux installer
install.ps1      Windows installer
INSTALL.md       Cross-platform setup guide
requirements.txt Python dependencies
.env.example     Example environment file
```

## Notes

- Keep `.env` out of git.
- Audio cache lives in `cache/`.
- Logs are written to `logs/bot.log`.
- The bot uses `ffmpeg` and Discord voice support, so make sure those system dependencies are installed.

## License

MIT. See `LICENSE`.
