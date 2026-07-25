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
- **Local audio caching** for faster repeat playback (intelligently cleaned)
- **Automatic cache cleanup**: Runs every 24 hours, removes files older than 7 days
- **Storage optimized for 24/7 operation**: Cache grows only while new content is played, old files auto-removed
- Rotating logs stored in `logs/` with 7-day retention
- Clean, consistent embeds
- Deafens itself by default when joining voice
- Fully slash-command based, no prefix commands
- For 24/7 hosting, use `systemd` or `PM2` on Linux, or Task Scheduler/NSSM on Windows

See [INSTALL.md](INSTALL.md) for full setup instructions.

## Notes

- Keep `.env` out of git.
- **Audio cache** (`cache/` directory):
  - Stores downloaded MP3 files for faster repeat playback
  - **Automatically cleaned every 24 hours** — removes files older than 7 days
  - At startup, removes any files that exceed 7-day age limit
  - Perfect for 24/7 operation: storage usage stays bounded and predictable
  - Frequently played songs stay cached, old ones are auto-removed
- **Logs** (`logs/bot.log`):
  - Rotating file handler keeps 7 days of logs
  - New log file each day, old ones auto-deleted after 7 days
- On Linux, the bot requires system `ffmpeg` and `libopus` for reliable Discord voice playback.
- **Spotify Support**: 
  - **Individual tracks** work with any Spotify account (free or premium)
  - **Playlists & Albums** require a PREMIUM Spotify account for direct API access
  - **Smart workaround for free accounts**: Bot attempts three fallback strategies:
    1. Try to fetch actual track list via alternative API method (might work in some cases)
    2. If available, get playlist metadata for partial info
    3. Search YouTube by playlist name as final fallback (tracks play from YouTube)
  - Users with free accounts can still use playlists, just with YouTube audio source

## License

MIT. See `LICENSE`.
