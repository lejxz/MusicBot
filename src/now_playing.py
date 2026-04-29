"""
Now Playing message management
"""
import discord
import logging
from typing import Optional, Dict
from datetime import datetime, timedelta
from src.queue import Track
from src.embeds import MusicEmbedManager


logger = logging.getLogger(__name__)


class NowPlayingManager:
    """Manages Now Playing messages in channels"""
    
    def __init__(self):
        self.messages: Dict[int, Dict] = {}  # guild_id -> {message_id, channel_id, timestamp}
    
    async def send_now_playing(
        self, 
        channel: discord.TextChannel, 
        track: Track,
        position: int = 0,
        duration: int = 0
    ) -> Optional[discord.Message]:
        """Send/update Now Playing message in channel
        
        Args:
            channel: Text channel to post in
            track: Current track
            position: Current playback position in seconds
            duration: Total track duration in seconds
        
        Returns:
            Sent message or None if failed
        """
        try:
            # Create embed
            embed = discord.Embed(
                title="🎵 Now Playing",
                description=f"**{track.title}**",
                color=discord.Color.blurple()
            )
            embed.add_field(name="Artist", value=track.artist, inline=False)
            embed.add_field(name="Source", value=track.platform_badge, inline=True)
            
            # Add progress bar if duration available
            if duration > 0:
                pos_min, pos_sec = divmod(position, 60)
                dur_min, dur_sec = divmod(duration, 60)
                
                # Create simple progress bar
                progress_ratio = position / duration if duration > 0 else 0
                bar_length = 20
                filled = int(bar_length * progress_ratio)
                bar = "█" * filled + "░" * (bar_length - filled)
                
                embed.add_field(
                    name="Progress",
                    value=f"`{bar}` {pos_min}:{pos_sec:02d} / {dur_min}:{dur_sec:02d}",
                    inline=False
                )
            
            if track.thumbnail:
                embed.set_thumbnail(url=track.thumbnail)
            
            embed.set_footer(text=f"Guild ID: {channel.guild.id}")
            embed.timestamp = discord.utils.utcnow()
            
            # Send message
            message = await channel.send(embed=embed)
            
            # Store message info
            self.messages[channel.guild.id] = {
                'message_id': message.id,
                'channel_id': channel.id,
                'timestamp': datetime.now()
            }
            
            logger.info(f"Sent Now Playing message in {channel.guild.id}")
            return message
            
        except discord.Forbidden:
            logger.warning(f"No permission to send Now Playing message in {channel.id}")
            return None
        except Exception as e:
            logger.exception(f"Failed to send Now Playing message")
            return None
    
    async def update_now_playing(
        self,
        guild: discord.Guild,
        track: Track,
        position: int = 0,
        duration: int = 0
    ) -> bool:
        """Update existing Now Playing message
        
        Args:
            guild: Guild to update message in
            track: Current track
            position: Current playback position
            duration: Total duration
        
        Returns:
            True if updated, False if failed
        """
        if guild.id not in self.messages:
            return False
        
        try:
            msg_info = self.messages[guild.id]
            channel = guild.get_channel(msg_info['channel_id'])
            
            if not channel:
                logger.warning(f"Channel {msg_info['channel_id']} not found in guild {guild.id}")
                del self.messages[guild.id]
                return False
            
            # Try to fetch and update message
            try:
                message = await channel.fetch_message(msg_info['message_id'])
                
                # Recreate embed
                embed = discord.Embed(
                    title="🎵 Now Playing",
                    description=f"**{track.title}**",
                    color=discord.Color.blurple()
                )
                embed.add_field(name="Artist", value=track.artist, inline=False)
                embed.add_field(name="Source", value=track.platform_badge, inline=True)
                
                if duration > 0:
                    pos_min, pos_sec = divmod(position, 60)
                    dur_min, dur_sec = divmod(duration, 60)
                    
                    progress_ratio = position / duration if duration > 0 else 0
                    bar_length = 20
                    filled = int(bar_length * progress_ratio)
                    bar = "█" * filled + "░" * (bar_length - filled)
                    
                    embed.add_field(
                        name="Progress",
                        value=f"`{bar}` {pos_min}:{pos_sec:02d} / {dur_min}:{dur_sec:02d}",
                        inline=False
                    )
                
                if track.thumbnail:
                    embed.set_thumbnail(url=track.thumbnail)
                
                embed.timestamp = discord.utils.utcnow()
                
                await message.edit(embed=embed)
                logger.debug(f"Updated Now Playing for guild {guild.id}")
                return True
                
            except discord.NotFound:
                logger.warning(f"Now Playing message {msg_info['message_id']} not found")
                del self.messages[guild.id]
                return False
                
        except Exception as e:
            logger.exception(f"Failed to update Now Playing message")
            return False
    
    async def delete_now_playing(self, guild: discord.Guild) -> bool:
        """Delete Now Playing message
        
        Args:
            guild: Guild to delete message from
        
        Returns:
            True if deleted, False if failed or not found
        """
        if guild.id not in self.messages:
            return False
        
        try:
            msg_info = self.messages[guild.id]
            channel = guild.get_channel(msg_info['channel_id'])
            
            if not channel:
                del self.messages[guild.id]
                return False
            
            try:
                message = await channel.fetch_message(msg_info['message_id'])
                await message.delete()
                logger.info(f"Deleted Now Playing message for guild {guild.id}")
            except discord.NotFound:
                logger.debug(f"Now Playing message already deleted")
            
            del self.messages[guild.id]
            return True
            
        except Exception as e:
            logger.exception(f"Failed to delete Now Playing message")
            return False
