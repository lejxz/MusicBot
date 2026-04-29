"""
Discord Music Bot - Main Bot File
"""
import discord
from discord.ext import commands, tasks
import logging
import os
import shutil
from pathlib import Path
from config import Config
from src.player import MusicPlayer
from src.logger import setup_logging, get_logger
from src.embeds import MusicEmbedManager
from src.cache import AudioCache
from commands.play import PlayCommand
from commands.playback import PlaybackCommands
from commands.queue import QueueCommands
from commands.audio import AudioCommands
from commands.utility import UtilityCommands
from events import EventHandlers, PlayerButtons


# Setup centralized logging with colors
setup_logging(level=logging.INFO, log_file=str(Config.LOG_DIR / "bot.log"))
logger = get_logger(__name__)


class MusicBot(commands.Cog):
    """Main Music Bot Cog"""
    
    def __init__(self, bot):
        self.bot = bot
        self.music_player = MusicPlayer(bot)
        self.cache = AudioCache()
        self.periodic_cache_cleanup.start()
    
    def cog_unload(self):
        """Stop background tasks when cog is unloaded"""
        self.periodic_cache_cleanup.cancel()
    
    @tasks.loop(hours=24)
    async def periodic_cache_cleanup(self):
        """Automatically clean up old cache files every 24 hours (for 24/7 efficiency)"""
        try:
            removed = await self.cache.clear_old_cache(max_age_days=7)
            total_size_mb = await self.cache.get_cache_size() / (1024 * 1024)
            logger.info(f"Cache cleanup: Removed {removed} old files. Cache size: {total_size_mb:.2f} MB")
        except Exception as e:
            logger.warning(f"Periodic cache cleanup failed: {e}")
    
    @periodic_cache_cleanup.before_loop
    async def before_cache_cleanup(self):
        """Ensure bot is ready before starting the cleanup loop"""
        await self.bot.wait_until_ready()
    

    # Play Command
    @discord.app_commands.command(name="play", description="Play a track from YouTube or Spotify")
    @discord.app_commands.describe(
        query="Song name, artist, YouTube URL, or Spotify link",
        source="Source preference: 'youtube' or 'spotify' (auto-detect if not specified)"
    )
    async def play(
        self, 
        interaction: discord.Interaction, 
        query: str,
        source: str = None
    ):
        """Play command with optional source preference"""
        # Validate source parameter
        if source and source.lower() not in ['youtube', 'spotify']:
            embed = MusicEmbedManager.create_error_embed(
                "Invalid source. Use 'youtube' or 'spotify' (or leave blank for auto-detect)"
            )
            await interaction.response.defer()
            await interaction.followup.send(embed=embed)
            return
        
        await PlayCommand.play(
            interaction, 
            query, 
            self.music_player, 
            source=source.lower() if source else None
        )
    
    # Playback Commands
    @discord.app_commands.command(name="pause", description="Pause current playback")
    async def pause(self, interaction: discord.Interaction):
        """Pause command"""
        await PlaybackCommands.pause(interaction, self.music_player)
    
    @discord.app_commands.command(name="resume", description="Resume paused playback")
    async def resume(self, interaction: discord.Interaction):
        """Resume command"""
        await PlaybackCommands.resume(interaction, self.music_player)
    
    @discord.app_commands.command(name="stop", description="Stop playback and clear queue")
    async def stop(self, interaction: discord.Interaction):
        """Stop command"""
        await PlaybackCommands.stop(interaction, self.music_player)
    
    @discord.app_commands.command(name="skip", description="Skip current track")
    async def skip(self, interaction: discord.Interaction):
        """Skip command"""
        await PlaybackCommands.skip(interaction, self.music_player)
    
    @discord.app_commands.command(name="previous", description="Play previous track")
    async def previous(self, interaction: discord.Interaction):
        """Previous command"""
        await PlaybackCommands.previous(interaction, self.music_player)
    
    # Queue Commands
    @discord.app_commands.command(name="queue", description="Display current queue")
    @discord.app_commands.describe(page="Page number (default: 1)")
    async def queue(self, interaction: discord.Interaction, page: int = 1):
        """Queue command"""
        await QueueCommands.queue(interaction, self.music_player, page)
    
    @discord.app_commands.command(name="remove", description="Remove track from queue")
    @discord.app_commands.describe(position="Position in queue")
    async def remove(self, interaction: discord.Interaction, position: int):
        """Remove command"""
        await QueueCommands.remove(interaction, self.music_player, position)
    
    @discord.app_commands.command(name="clear", description="Clear entire queue")
    async def clear(self, interaction: discord.Interaction):
        """Clear command"""
        await QueueCommands.clear(interaction, self.music_player)
    
    @discord.app_commands.command(name="shuffle", description="Shuffle queue")
    async def shuffle(self, interaction: discord.Interaction):
        """Shuffle command"""
        await QueueCommands.shuffle(interaction, self.music_player)
    
    @discord.app_commands.command(name="loop", description="Toggle loop mode")
    async def loop(self, interaction: discord.Interaction):
        """Loop command"""
        await QueueCommands.loop(interaction, self.music_player)
    
    @discord.app_commands.command(name="move", description="Reorder tracks in queue")
    @discord.app_commands.describe(
        from_pos="Current position",
        to_pos="New position"
    )
    async def move(self, interaction: discord.Interaction, from_pos: int, to_pos: int):
        """Move command"""
        await QueueCommands.move(interaction, self.music_player, from_pos, to_pos)
    
    # Audio Commands
    @discord.app_commands.command(name="volume", description="Adjust playback volume")
    @discord.app_commands.describe(level="Volume level (0-100)")
    async def volume(self, interaction: discord.Interaction, level: int):
        """Volume command"""
        await AudioCommands.volume(interaction, self.music_player, level)
    
    @discord.app_commands.command(name="seek", description="Jump to specific timestamp")
    @discord.app_commands.describe(time="Time in format mm:ss or seconds")
    async def seek(self, interaction: discord.Interaction, time: str):
        """Seek command"""
        await AudioCommands.seek(interaction, self.music_player, time)
    
    @discord.app_commands.command(name="lyrics", description="Fetch track lyrics")
    @discord.app_commands.describe(song="Song name (optional, uses current if not specified)")
    async def lyrics(self, interaction: discord.Interaction, song: str = None):
        """Lyrics command"""
        await AudioCommands.lyrics(interaction, self.music_player, song)
    
    # Utility Commands
    @discord.app_commands.command(name="np", description="Show currently playing track")
    async def now_playing(self, interaction: discord.Interaction):
        """Now playing command"""
        await UtilityCommands.now_playing(interaction, self.music_player)
    
    @discord.app_commands.command(name="join", description="Join your voice channel")
    async def join(self, interaction: discord.Interaction):
        """Join command"""
        await UtilityCommands.join(interaction, self.music_player)
    
    @discord.app_commands.command(name="leave", description="Leave voice channel")
    async def leave(self, interaction: discord.Interaction):
        """Leave command"""
        await UtilityCommands.leave(interaction, self.music_player)
    
    @discord.app_commands.command(name="help", description="Show all available commands")
    async def help(self, interaction: discord.Interaction):
        """Help command"""
        await UtilityCommands.help(interaction)
    
    @discord.app_commands.command(name="ping", description="Check bot latency")
    async def ping(self, interaction: discord.Interaction):
        """Ping command"""
        await UtilityCommands.ping(interaction, self.bot)
    
    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        """Handle voice state updates"""
        await EventHandlers.on_voice_state_update(member, before, after, self.bot, self.music_player)


async def load_cogs(bot):
    """Load bot cogs"""
    await bot.add_cog(MusicBot(bot))


async def main():
    """Main bot function"""
    # Create bot with slash commands intent
    intents = discord.Intents.default()
    intents.message_content = True
    intents.voice_states = True
    intents.guild_messages = True
    
    # Slash-command only bot: no text prefix commands are registered.
    bot = commands.Bot(command_prefix=lambda *_: [], intents=intents, help_command=None)
    
    @bot.event
    async def on_ready():
        await EventHandlers.on_ready(bot)
        await bot.tree.sync()  # Sync slash commands
        logger.info("Synced slash commands")
        logger.info("FFmpeg on PATH: %s", bool(shutil.which("ffmpeg")))
        logger.info("Opus loaded: %s", discord.opus.is_loaded())
    
    # Load cogs
    await load_cogs(bot)
    
    # Initialize cache (startup cleanup of files older than 7 days)
    try:
        cache = AudioCache()
        removed = await cache.clear_old_cache(max_age_days=7)
        cache_size_mb = await cache.get_cache_size() / (1024 * 1024)
        logger.info(f"Cache initialized: Removed {removed} old files. Current size: {cache_size_mb:.2f} MB")
    except Exception as e:
        logger.warning("Cache initialization failed: %s", e)
    
    # Run bot
    try:
        logger.info("Starting bot")
        await bot.start(Config.DISCORD_TOKEN)
    except KeyboardInterrupt:
        logger.info("Bot shutting down")
        await bot.close()


if __name__ == "__main__":
    import asyncio
    
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n🛑 Bot stopped")
