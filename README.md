lets redo it, as it will only be run locally and a copy of it in github. The music bot will include all necessary commands, using slash commands only from discord, no prefix.

See [INSTALL.md](INSTALL.md) for final cross-platform installation instructions.

🎵 Core Playback
/play <song/URL> – Plays a track from YouTube, Spotify

/pause – Pauses the current track.

/resume – Resumes paused playback.

/stop – Stops playback and clears the queue.

/skip – Skips the current track.

/previous – Plays the previous track (optional but useful).

📋 Queue Management
/queue – Displays the current song queue.

/remove <position> – Removes a specific track from the queue.

/clear – Clears the entire queue.

/shuffle – Randomizes the order of songs in the queue.

/loop – Toggles looping (single track or entire queue).

/move <from> <to> – Reorders tracks in the queue.

🔊 Audio Controls
/volume <level> – Adjusts playback volume.

/seek <time> – Jumps to a specific timestamp in the current track.

/lyrics <song> – Fetches lyrics for the current or specified track.

⚙️ Utility & Info
/np (Now Playing) – Shows details of the current track.

/join – Makes the bot join your voice channel.

/leave – Disconnects the bot from the voice channel.

/help – Lists all available commands.

/ping – Checks bot latency.


The music bot should be multi-source with both Spotify and YouTube support, including albums and playlists.


Capability	Details
🎛️ Dynamic - Embeds	Auto-refreshing "Now Playing" cards with cover art, platform badges, queue countdowns, and localized metadata.
🪄 Smart Queue	- Instant mix-ins, sequential preloading, shuffle with DJ-only guardrails, and playlist collapsing to keep channels tidy.
🔁 Loop Modes	- Three-way loop toggle: Off, Track Repeat (endless current song), or Queue Repeat (restart queue when finished).
🎲 Autoplay Engine	- Genre-aware autoplay with intelligent recommender  and the bot automatically queues matching music when your queue ends, filtering out tutorials, podcasts, and non-music content with smart duration and keyword detection.
💾 Local Audio Cache	- All tracks are pre-downloaded and cached locally to eliminate stream interruptions, network lag, and voice crackling—delivering buffer-free playback even during peak Discord load or ISP throttling.
🛡️ Resilient Playback	- Voice connection watchdog, stream retry logic, idle auto-disconnect, and graceful SIGINT shutdown.
🧠 Localization -	Cached translations via node-json-db with runtime language switching and fallback logic.
📜 Static Lyrics	- Fetches lyrics from Genius (web scraping) with LRCLIB fallback—button-only display with pagination support.



├── commands/           # Slash command handlers (play, help, search, language, ...)
├── events/             # Button & modal controllers for playback UI
├── src/                # Core services: MusicPlayer, MusicEmbedManager, providers
├── config.js           # Central configuration + env fallbacks
├── index.js            # Bot bootstrap, client wiring, voice auto-cleanup
├── LICENSE             # MIT License
├── PRIVACY_POLICY.md   # Data handling details
└── TERMS_OF_SERVICE.md # Acceptable use guidelines