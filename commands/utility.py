"""
Utility and info commands (np, join, leave, help, ping)
"""
import discord
import time
import logging
from src.embeds import MusicEmbedManager
from src.now_playing import NowPlayingManager


logger = logging.getLogger(__name__)

# Global now playing manager
now_playing_manager = NowPlayingManager()


class UtilityCommands:
    """Utility and info commands"""
    
    @staticmethod
    async def now_playing(interaction: discord.Interaction, music_player, announce: bool = False):
        """Show details of the current track
        
        Args:
            announce: If True, post to channel and auto-update; if False, show as reply
        """
        await interaction.response.defer()
        
        try:
            player = music_player.get_player(interaction.guild_id)
            
            if not player.current_track:
                embed = MusicEmbedManager.create_error_embed("No track is currently playing")
                await interaction.followup.send(embed=embed)
                return
            
            track = player.current_track
            
            if announce:
                # Send as channel message (now playing announcement)
                message = await now_playing_manager.send_now_playing(
                    interaction.channel,
                    track,
                    position=0,
                    duration=track.duration
                )
                
                if message:
                    embed = MusicEmbedManager.create_info_embed(
                        "📢 Now Playing",
                        f"Sent Now Playing message to {interaction.channel.mention}"
                    )
                else:
                    embed = MusicEmbedManager.create_error_embed("Failed to send Now Playing message")
                
                await interaction.followup.send(embed=embed)
            else:
                # Show as inline reply
                embed = MusicEmbedManager.create_now_playing_embed(
                    track,
                    queue_size=len(player.queue.tracks),
                    loop_mode=player.queue.loop_mode
                )
                await interaction.followup.send(embed=embed)
        
        except Exception as e:
            logger.exception("now_playing failed")
            embed = MusicEmbedManager.create_error_embed(f"Error: {str(e)}")
            await interaction.followup.send(embed=embed)
    
    @staticmethod
    async def join(interaction: discord.Interaction, music_player):
        """Make the bot join your voice channel"""
        await interaction.response.defer()
        logger.info("/join invoked by %s in guild %s", interaction.user, interaction.guild_id)
        
        try:
            if not interaction.user.voice:
                embed = MusicEmbedManager.create_error_embed(
                    "You must be in a voice channel"
                )
                await interaction.followup.send(embed=embed)
                return
            
            player = music_player.get_player(interaction.guild_id)
            
            if player.voice_client:
                embed = MusicEmbedManager.create_info_embed(
                    "✅ Already Connected",
                    f"Bot is already connected to {player.voice_client.channel.mention}"
                )
                await interaction.followup.send(embed=embed)
                return
            
            channel = interaction.user.voice.channel
            player.voice_client = await channel.connect(self_deaf=True)
            logger.info("Joined voice channel %s in guild %s", channel, interaction.guild_id)
            
            embed = MusicEmbedManager.create_info_embed(
                "✅ Joined",
                f"Bot joined {channel.mention}"
            )
            await interaction.followup.send(embed=embed)
        
        except Exception as e:
            logger.exception("/join failed")
            embed = MusicEmbedManager.create_error_embed(f"Error: {str(e)}")
            await interaction.followup.send(embed=embed)
    
    @staticmethod
    async def leave(interaction: discord.Interaction, music_player):
        """Disconnect the bot from the voice channel"""
        await interaction.response.defer()
        logger.info("/leave invoked by %s in guild %s", interaction.user, interaction.guild_id)
        
        try:
            player = music_player.get_player(interaction.guild_id)
            
            if not player.voice_client:
                embed = MusicEmbedManager.create_error_embed(
                    "Bot is not connected to a voice channel"
                )
                await interaction.followup.send(embed=embed)
                return
            
            channel = player.voice_client.channel
            await player.disconnect()
            logger.info("Left voice channel %s in guild %s", channel, interaction.guild_id)
            
            embed = MusicEmbedManager.create_info_embed(
                "✅ Left",
                f"Bot left {channel.mention}"
            )
            await interaction.followup.send(embed=embed)
        
        except Exception as e:
            logger.exception("/leave failed")
            embed = MusicEmbedManager.create_error_embed(f"Error: {str(e)}")
            await interaction.followup.send(embed=embed)
    
    @staticmethod
    async def help(interaction: discord.Interaction):
        """List all available commands"""
        await interaction.response.defer()
        
        try:
            embed = discord.Embed(
                title="🎵 Music Bot Commands",
                description="Use `/` followed by a command name",
                color=discord.Color.blurple()
            )
            
            embed.add_field(
                name="🎵 Core Playback",
                value="""
                `/play` - Play a track from YouTube or Spotify
                `/pause` - Pause current playback
                `/resume` - Resume paused playback
                `/stop` - Stop playback and clear queue
                `/skip` - Skip current track
                `/previous` - Play previous track
                """,
                inline=False
            )
            
            embed.add_field(
                name="📋 Queue Management",
                value="""
                `/queue` - Display current queue
                `/remove` - Remove track from queue
                `/clear` - Clear entire queue
                `/shuffle` - Randomize queue order
                `/loop` - Toggle loop mode
                `/move` - Reorder tracks
                """,
                inline=False
            )
            
            embed.add_field(
                name="🔊 Audio Controls",
                value="""
                `/volume` - Adjust playback volume
                `/seek` - Jump to timestamp
                `/lyrics` - Fetch track lyrics
                """,
                inline=False
            )
            
            embed.add_field(
                name="⚙️ Utility",
                value="""
                `/np` - Show now playing
                `/join` - Join voice channel
                `/leave` - Leave voice channel
                `/ping` - Check bot latency
                """,
                inline=False
            )
            
            embed.set_footer(text="Multi-source player with YouTube & Spotify support")
            embed.timestamp = discord.utils.utcnow()
            
            await interaction.followup.send(embed=embed)
        
        except Exception as e:
            embed = MusicEmbedManager.create_error_embed(f"Error: {str(e)}")
            await interaction.followup.send(embed=embed)
    
    @staticmethod
    async def ping(interaction: discord.Interaction, bot):
        """Check bot latency"""
        await interaction.response.defer()
        
        try:
            # Measure websocket latency
            ws_latency = round(bot.latency * 1000)
            
            embed = MusicEmbedManager.create_info_embed(
                "🏓 Pong!",
                f"Websocket latency: **{ws_latency}ms**"
            )
            
            await interaction.followup.send(embed=embed)
        
        except Exception as e:
            embed = MusicEmbedManager.create_error_embed(f"Error: {str(e)}")
            await interaction.followup.send(embed=embed)
