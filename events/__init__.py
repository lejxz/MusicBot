"""
Events and Button Handlers - Interactive UI for playback
"""
import discord
from discord.ext import commands
import logging


logger = logging.getLogger(__name__)


class PlayerButtons(discord.ui.View):
    """Persistent buttons for music player"""
    
    def __init__(self, music_player):
        super().__init__(timeout=None)
        self.music_player = music_player
    
    @discord.ui.button(label="⏮️", style=discord.ButtonStyle.secondary, custom_id="previous")
    async def previous_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Previous button"""
        from commands.playback import PlaybackCommands
        await PlaybackCommands.previous(interaction, self.music_player)
    
    @discord.ui.button(label="⏸️", style=discord.ButtonStyle.primary, custom_id="pause")
    async def pause_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Pause button"""
        from commands.playback import PlaybackCommands
        await PlaybackCommands.pause(interaction, self.music_player)
    
    @discord.ui.button(label="⏯️", style=discord.ButtonStyle.primary, custom_id="resume")
    async def resume_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Resume button"""
        from commands.playback import PlaybackCommands
        await PlaybackCommands.resume(interaction, self.music_player)
    
    @discord.ui.button(label="⏭️", style=discord.ButtonStyle.secondary, custom_id="skip")
    async def skip_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Skip button"""
        from commands.playback import PlaybackCommands
        await PlaybackCommands.skip(interaction, self.music_player)
    
    @discord.ui.button(label="⏹️", style=discord.ButtonStyle.danger, custom_id="stop")
    async def stop_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Stop button"""
        from commands.playback import PlaybackCommands
        await PlaybackCommands.stop(interaction, self.music_player)


class EventHandlers:
    """Event handlers for bot lifecycle"""
    
    @staticmethod
    async def on_ready(bot):
        """Bot ready event"""
        logger.info("%s is now running", bot.user)
        await bot.change_presence(
            activity=discord.Activity(
                type=discord.ActivityType.listening,
                name="/help for commands"
            )
        )
    
    @staticmethod
    async def on_voice_state_update(member, before, after, bot, music_player):
        """Handle voice state updates"""
        logger.info(
            "Voice state update: member=%s before=%s after=%s",
            member,
            getattr(before.channel, 'name', None),
            getattr(after.channel, 'name', None),
        )
        # Auto-disconnect if all members left
        if member.bot:
            return
        
        if before.channel and not after.channel:
            # User left voice channel
            if before.channel.guild and bot.user in before.channel.members:
                # Check if only bot remains
                non_bot_members = [m for m in before.channel.members if not m.bot]
                if not non_bot_members:
                    player = music_player.get_player(before.channel.guild.id)
                    await player.disconnect()
                    logger.info("Auto-disconnected from %s", before.channel.name)
