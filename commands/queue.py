"""
Queue management commands with reaction-based pagination
"""
import discord
import logging
from src.embeds import MusicEmbedManager


logger = logging.getLogger(__name__)

# Reaction emojis for pagination
FIRST_PAGE_EMOJI = "⏮️"
PREV_PAGE_EMOJI = "◀️"
NEXT_PAGE_EMOJI = "▶️"
LAST_PAGE_EMOJI = "⏭️"
DELETE_EMOJI = "🗑️"
PAGINATION_EMOJIS = [FIRST_PAGE_EMOJI, PREV_PAGE_EMOJI, NEXT_PAGE_EMOJI, LAST_PAGE_EMOJI, DELETE_EMOJI]


class QueuePaginationView(discord.ui.View):
    """View for queue pagination with buttons/reactions"""
    
    def __init__(self, interaction, all_tracks, current_index, per_page=10):
        super().__init__(timeout=300)
        
        self.interaction = interaction
        self.all_tracks = all_tracks
        self.current_index = current_index
        self.per_page = per_page
        self.current_page = 1
        self.total_pages = max(1, (len(all_tracks) + per_page - 1) // per_page)
        self.message = None
        
        # Update button states
        self._update_button_states()
    
    def _update_button_states(self):
        """Enable/disable buttons based on current page"""
        self.first_page_button.disabled = self.current_page <= 1
        self.prev_page_button.disabled = self.current_page <= 1
        self.next_page_button.disabled = self.current_page >= self.total_pages
        self.last_page_button.disabled = self.current_page >= self.total_pages
    
    def _create_embed(self) -> discord.Embed:
        """Create queue embed for current page"""
        start_idx = (self.current_page - 1) * self.per_page
        end_idx = start_idx + self.per_page
        
        embed = discord.Embed(
            title=f"📋 Queue ({len(self.all_tracks)} tracks)",
            color=discord.Color.blurple()
        )
        
        for i, track in enumerate(self.all_tracks[start_idx:end_idx], start=start_idx + 1):
            duration_min, duration_sec = divmod(track.duration, 60)
            current_marker = "▶️ " if i - 1 == self.current_index else ""
            embed.add_field(
                name=f"{current_marker}{i}. {track.title}",
                value=f"{track.artist} • {duration_min}:{duration_sec:02d}",
                inline=False
            )
        
        total_duration = sum(t.duration for t in self.all_tracks)
        duration_hours = total_duration // 3600
        duration_mins = (total_duration % 3600) // 60
        
        embed.set_footer(
            text=f"Page {self.current_page}/{self.total_pages} | Total: {duration_hours}h {duration_mins}m"
        )
        embed.timestamp = discord.utils.utcnow()
        
        return embed
    
    @discord.ui.button(emoji="⏮️", style=discord.ButtonStyle.secondary)
    async def first_page_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Go to first page"""
        if interaction.user != self.interaction.user:
            await interaction.response.defer()
            return
        
        self.current_page = 1
        self._update_button_states()
        embed = self._create_embed()
        await interaction.response.edit_message(embed=embed, view=self)
    
    @discord.ui.button(emoji="◀️", style=discord.ButtonStyle.primary)
    async def prev_page_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Go to previous page"""
        if interaction.user != self.interaction.user:
            await interaction.response.defer()
            return
        
        self.current_page = max(1, self.current_page - 1)
        self._update_button_states()
        embed = self._create_embed()
        await interaction.response.edit_message(embed=embed, view=self)
    
    @discord.ui.button(emoji="▶️", style=discord.ButtonStyle.primary)
    async def next_page_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Go to next page"""
        if interaction.user != self.interaction.user:
            await interaction.response.defer()
            return
        
        self.current_page = min(self.total_pages, self.current_page + 1)
        self._update_button_states()
        embed = self._create_embed()
        await interaction.response.edit_message(embed=embed, view=self)
    
    @discord.ui.button(emoji="⏭️", style=discord.ButtonStyle.secondary)
    async def last_page_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Go to last page"""
        if interaction.user != self.interaction.user:
            await interaction.response.defer()
            return
        
        self.current_page = self.total_pages
        self._update_button_states()
        embed = self._create_embed()
        await interaction.response.edit_message(embed=embed, view=self)
    
    @discord.ui.button(emoji="🗑️", style=discord.ButtonStyle.danger)
    async def delete_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Delete queue message"""
        if interaction.user != self.interaction.user:
            await interaction.response.defer()
            return
        
        try:
            await self.message.delete()
        except discord.NotFound:
            pass
        except discord.Forbidden:
            await interaction.response.send_message(
                "No permission to delete message",
                ephemeral=True
            )
            return
        
        await interaction.response.defer()


class QueueCommands:
    """Queue management commands"""
    
    @staticmethod
    async def queue(interaction: discord.Interaction, music_player, page: int = None):
        """Display the current queue with reaction-based pagination"""
        await interaction.response.defer()
        
        try:
            player = music_player.get_player(interaction.guild_id)
            all_tracks = await player.queue.get_all()
            
            if not all_tracks:
                embed = MusicEmbedManager.create_info_embed(
                    "📋 Queue",
                    "Queue is empty"
                )
                await interaction.followup.send(embed=embed)
                return
            
            # Create pagination view
            per_page = 10
            view = QueuePaginationView(
                interaction,
                all_tracks,
                player.queue.current_index,
                per_page=per_page
            )
            
            # Set starting page if specified
            if page:
                total_pages = max(1, (len(all_tracks) + per_page - 1) // per_page)
                view.current_page = max(1, min(page, total_pages))
                view._update_button_states()
            
            embed = view._create_embed()
            message = await interaction.followup.send(embed=embed, view=view)
            view.message = message
        
        except Exception as e:
            logger.exception("queue failed")
            embed = MusicEmbedManager.create_error_embed(f"Error: {str(e)}")
            await interaction.followup.send(embed=embed)
    
    @staticmethod
    async def remove(interaction: discord.Interaction, music_player, position: int):
        """Remove a track from the queue"""
        await interaction.response.defer()
        
        try:
            player = music_player.get_player(interaction.guild_id)
            
            # Convert to 0-based index
            index = position - 1
            removed_track = await player.queue.remove(index)
            
            if not removed_track:
                embed = MusicEmbedManager.create_error_embed(
                    f"Invalid position: {position}"
                )
                await interaction.followup.send(embed=embed)
                return
            
            embed = MusicEmbedManager.create_info_embed(
                "🗑️ Removed from Queue",
                f"Removed: **{removed_track.title}**"
            )
            await interaction.followup.send(embed=embed)
        
        except Exception as e:
            embed = MusicEmbedManager.create_error_embed(f"Error: {str(e)}")
            await interaction.followup.send(embed=embed)
    
    @staticmethod
    async def clear(interaction: discord.Interaction, music_player):
        """Clear the entire queue"""
        await interaction.response.defer()
        
        try:
            player = music_player.get_player(interaction.guild_id)
            await player.queue.clear()
            
            embed = MusicEmbedManager.create_info_embed(
                "🧹 Queue Cleared",
                "All tracks have been removed from the queue"
            )
            await interaction.followup.send(embed=embed)
        
        except Exception as e:
            embed = MusicEmbedManager.create_error_embed(f"Error: {str(e)}")
            await interaction.followup.send(embed=embed)
    
    @staticmethod
    async def shuffle(interaction: discord.Interaction, music_player):
        """Shuffle the queue"""
        await interaction.response.defer()
        
        try:
            player = music_player.get_player(interaction.guild_id)
            queue_size = await player.queue.size()
            
            if queue_size < 2:
                embed = MusicEmbedManager.create_error_embed(
                    "Queue must have at least 2 tracks to shuffle"
                )
                await interaction.followup.send(embed=embed)
                return
            
            await player.queue.shuffle()
            
            embed = MusicEmbedManager.create_info_embed(
                "🔀 Queue Shuffled",
                f"Shuffled {queue_size} tracks"
            )
            await interaction.followup.send(embed=embed)
        
        except Exception as e:
            embed = MusicEmbedManager.create_error_embed(f"Error: {str(e)}")
            await interaction.followup.send(embed=embed)
    
    @staticmethod
    async def loop(interaction: discord.Interaction, music_player):
        """Toggle loop mode"""
        await interaction.response.defer()
        
        try:
            player = music_player.get_player(interaction.guild_id)
            new_mode = player.queue.toggle_loop()
            
            mode_names = ["🔓 Off", "🔂 Track Repeat", "🔁 Queue Repeat"]
            
            embed = MusicEmbedManager.create_info_embed(
                "🔁 Loop Mode",
                f"Loop mode set to: {mode_names[new_mode]}"
            )
            await interaction.followup.send(embed=embed)
        
        except Exception as e:
            embed = MusicEmbedManager.create_error_embed(f"Error: {str(e)}")
            await interaction.followup.send(embed=embed)
    
    @staticmethod
    async def move(interaction: discord.Interaction, music_player, from_pos: int, to_pos: int):
        """Move a track in the queue"""
        await interaction.response.defer()
        
        try:
            player = music_player.get_player(interaction.guild_id)
            
            success = await player.queue.move(from_pos - 1, to_pos - 1)
            
            if not success:
                embed = MusicEmbedManager.create_error_embed(
                    f"Invalid positions: from {from_pos} to {to_pos}"
                )
                await interaction.followup.send(embed=embed)
                return
            
            embed = MusicEmbedManager.create_info_embed(
                "📍 Track Moved",
                f"Moved track from position {from_pos} to {to_pos}"
            )
            await interaction.followup.send(embed=embed)
        
        except Exception as e:
            embed = MusicEmbedManager.create_error_embed(f"Error: {str(e)}")
            await interaction.followup.send(embed=embed)
