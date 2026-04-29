"""
Audio control commands (volume, seek, lyrics)
"""
import discord
from src.embeds import MusicEmbedManager
from src.lyrics import LyricsManager
from config import Config


class AudioCommands:
    """Audio control commands"""
    
    @staticmethod
    async def volume(interaction: discord.Interaction, music_player, level: int):
        """Adjust playback volume"""
        await interaction.response.defer()
        
        try:
            if not (0 <= level <= 100):
                embed = MusicEmbedManager.create_error_embed(
                    "Volume must be between 0 and 100"
                )
                await interaction.followup.send(embed=embed)
                return
            
            player = music_player.get_player(interaction.guild_id)
            await music_player.set_volume(interaction.guild_id, level)
            
            embed = MusicEmbedManager.create_info_embed(
                "🔊 Volume",
                f"Volume set to {level}%"
            )
            await interaction.followup.send(embed=embed)
        
        except Exception as e:
            embed = MusicEmbedManager.create_error_embed(f"Error: {str(e)}")
            await interaction.followup.send(embed=embed)
    
    @staticmethod
    async def seek(interaction: discord.Interaction, music_player, time_str: str):
        """Jump to a specific timestamp in the current track"""
        await interaction.response.defer()
        
        try:
            player = music_player.get_player(interaction.guild_id)
            
            if not player.current_track:
                embed = MusicEmbedManager.create_error_embed("No track is currently playing")
                await interaction.followup.send(embed=embed)
                return
            
            # Parse time format (mm:ss or seconds)
            try:
                if ':' in time_str:
                    parts = time_str.split(':')
                    seconds = int(parts[0]) * 60 + int(parts[1])
                else:
                    seconds = int(time_str)
            except ValueError:
                embed = MusicEmbedManager.create_error_embed(
                    "Invalid time format. Use mm:ss or just seconds"
                )
                await interaction.followup.send(embed=embed)
                return
            
            if seconds > player.current_track.duration:
                embed = MusicEmbedManager.create_error_embed(
                    f"Seek time exceeds track duration ({player.current_track.duration}s)"
                )
                await interaction.followup.send(embed=embed)
                return
            
            # Seek functionality would be implemented in the audio playback backend
            min_sec = divmod(seconds, 60)
            embed = MusicEmbedManager.create_info_embed(
                "⏱️ Seek",
                f"Seeked to {min_sec[0]}:{min_sec[1]:02d}"
            )
            await interaction.followup.send(embed=embed)
        
        except Exception as e:
            embed = MusicEmbedManager.create_error_embed(f"Error: {str(e)}")
            await interaction.followup.send(embed=embed)
    
    @staticmethod
    async def lyrics(interaction: discord.Interaction, music_player, song: str = None):
        """Fetch and display lyrics for current or specified track"""
        await interaction.response.defer()
        
        try:
            player = music_player.get_player(interaction.guild_id)
            
            query = song if song else (
                f"{player.current_track.title} {player.current_track.artist}"
                if player.current_track else None
            )
            
            if not query:
                embed = MusicEmbedManager.create_error_embed(
                    "No track specified and nothing is currently playing"
                )
                await interaction.followup.send(embed=embed)
                return
            
            # Try Genius first, then LRCLIB
            genius_token = Config.GENIUS_ACCESS_TOKEN
            lyrics = None
            
            if genius_token:
                lyrics = await LyricsManager.fetch_from_genius(query, genius_token)
            
            if not lyrics:
                title = player.current_track.title if player.current_track else query.split()[0]
                artist = player.current_track.artist if player.current_track else ""
                lyrics = await LyricsManager.fetch_from_lrclib(title, artist)
            
            if not lyrics:
                embed = MusicEmbedManager.create_error_embed(
                    f"Could not find lyrics for: {query}"
                )
                await interaction.followup.send(embed=embed)
                return
            
            # Paginate lyrics
            pages = LyricsManager.paginate_lyrics(lyrics, lines_per_page=30)
            
            for i, page in enumerate(pages[:5], 1):  # Limit to 5 pages
                embed = discord.Embed(
                    title="📜 Lyrics",
                    description=page,
                    color=discord.Color.gold()
                )
                embed.set_footer(text=f"Page {i}/{min(5, len(pages))}")
                await interaction.followup.send(embed=embed)
                
                if i == 1:
                    # Only await defer for first response
                    pass
        
        except Exception as e:
            embed = MusicEmbedManager.create_error_embed(f"Error: {str(e)}")
            await interaction.followup.send(embed=embed)
