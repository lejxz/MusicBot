"""
Playback commands - Control playback (pause, resume, stop, skip, previous)
"""
import discord
from src.embeds import MusicEmbedManager


class PlaybackCommands:
    """Playback control commands"""
    
    @staticmethod
    async def pause(interaction: discord.Interaction, music_player):
        """Pause current playback"""
        await interaction.response.defer()
        
        try:
            player = music_player.get_player(interaction.guild_id)
            
            if not player.is_playing:
                embed = MusicEmbedManager.create_error_embed("No track is currently playing")
                await interaction.followup.send(embed=embed)
                return
            
            paused = await player.pause()
            if not paused:
                embed = MusicEmbedManager.create_error_embed("No track is currently playing")
                await interaction.followup.send(embed=embed)
                return

            embed = MusicEmbedManager.create_info_embed(
                "⏸️ Paused",
                f"Paused: **{player.current_track.title}**"
            )
            await interaction.followup.send(embed=embed)
        
        except Exception as e:
            embed = MusicEmbedManager.create_error_embed(f"Error: {str(e)}")
            await interaction.followup.send(embed=embed)
    
    @staticmethod
    async def resume(interaction: discord.Interaction, music_player):
        """Resume playback"""
        await interaction.response.defer()
        
        try:
            player = music_player.get_player(interaction.guild_id)
            
            if not (player.is_paused and player.current_track):
                embed = MusicEmbedManager.create_error_embed("No paused track to resume")
                await interaction.followup.send(embed=embed)
                return
            
            resumed = await player.resume()
            if not resumed:
                embed = MusicEmbedManager.create_error_embed("No paused track to resume")
                await interaction.followup.send(embed=embed)
                return

            embed = MusicEmbedManager.create_info_embed(
                "▶️ Resumed",
                f"Resumed: **{player.current_track.title}**"
            )
            await interaction.followup.send(embed=embed)
        
        except Exception as e:
            embed = MusicEmbedManager.create_error_embed(f"Error: {str(e)}")
            await interaction.followup.send(embed=embed)
    
    @staticmethod
    async def stop(interaction: discord.Interaction, music_player):
        """Stop playback and clear queue"""
        await interaction.response.defer()
        
        try:
            player = music_player.get_player(interaction.guild_id)
            await player.stop()
            
            embed = MusicEmbedManager.create_info_embed(
                "⏹️ Stopped",
                "Playback stopped and queue cleared"
            )
            await interaction.followup.send(embed=embed)
        
        except Exception as e:
            embed = MusicEmbedManager.create_error_embed(f"Error: {str(e)}")
            await interaction.followup.send(embed=embed)
    
    @staticmethod
    async def skip(interaction: discord.Interaction, music_player):
        """Skip current track"""
        await interaction.response.defer()
        
        try:
            player = music_player.get_player(interaction.guild_id)
            
            if not player.current_track:
                embed = MusicEmbedManager.create_error_embed("No track is currently playing")
                await interaction.followup.send(embed=embed)
                return
            
            skipped_track = player.current_track
            next_track = await player.skip()
            
            embed = MusicEmbedManager.create_info_embed(
                "⏭️ Skipped",
                f"Skipped: **{skipped_track.title}**"
            )
            
            if next_track:
                embed.add_field(
                    name="Now Playing",
                    value=f"**{next_track.title}**\nby *{next_track.artist}*"
                )
            else:
                embed.add_field(
                    name="Queue",
                    value="Queue is empty"
                )
            
            await interaction.followup.send(embed=embed)
        
        except Exception as e:
            embed = MusicEmbedManager.create_error_embed(f"Error: {str(e)}")
            await interaction.followup.send(embed=embed)
    
    @staticmethod
    async def previous(interaction: discord.Interaction, music_player):
        """Play previous track"""
        await interaction.response.defer()
        
        try:
            player = music_player.get_player(interaction.guild_id)
            
            prev_track = await player.previous()
            
            if not prev_track:
                embed = MusicEmbedManager.create_error_embed("No previous track available")
                await interaction.followup.send(embed=embed)
                return
            
            embed = MusicEmbedManager.create_info_embed(
                "⏮️ Previous Track",
                f"Playing: **{prev_track.title}**\nby *{prev_track.artist}*"
            )
            if prev_track.thumbnail:
                embed.set_thumbnail(url=prev_track.thumbnail)
            
            await interaction.followup.send(embed=embed)
        
        except Exception as e:
            embed = MusicEmbedManager.create_error_embed(f"Error: {str(e)}")
            await interaction.followup.send(embed=embed)
