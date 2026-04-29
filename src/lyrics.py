"""
Lyrics manager for fetching and displaying lyrics
"""
import aiohttp
from typing import Optional
from bs4 import BeautifulSoup


class LyricsManager:
    """Manages lyrics fetching and display"""
    
    @staticmethod
    async def fetch_from_genius(query: str, token: str) -> Optional[str]:
        """Fetch lyrics from Genius API"""
        async with aiohttp.ClientSession() as session:
            headers = {
                'Authorization': f'Bearer {token}',
                'User-Agent': 'Discord-Music-Bot'
            }
            params = {'q': query}
            
            try:
                async with session.get(
                    'https://api.genius.com/search',
                    headers=headers,
                    params=params
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        hits = data.get('response', {}).get('hits', [])
                        if not hits:
                            return None
                        
                        song_url = hits[0]['result'].get('url')
                        return await LyricsManager._scrape_lyrics(song_url)
            except Exception as e:
                print(f"Genius error: {e}")
        
        return None
    
    @staticmethod
    async def fetch_from_lrclib(title: str, artist: str) -> Optional[str]:
        """Fetch lyrics from LRCLIB (fallback)"""
        async with aiohttp.ClientSession() as session:
            params = {
                'track_name': title,
                'artist_name': artist,
            }
            
            try:
                async with session.get(
                    'https://lrclib.net/api/get',
                    params=params,
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        return data.get('lyrics')
            except Exception as e:
                print(f"LRCLIB error: {e}")
        
        return None
    
    @staticmethod
    async def _scrape_lyrics(url: str) -> Optional[str]:
        """Scrape lyrics from Genius URL"""
        async with aiohttp.ClientSession() as session:
            try:
                async with session.get(url) as resp:
                    if resp.status == 200:
                        html = await resp.text()
                        soup = BeautifulSoup(html, 'html.parser')
                        
                        # Find lyrics containers
                        lyrics_divs = soup.find_all('div', {'class': 'Lyrics__Container__0-2-3'})
                        
                        if lyrics_divs:
                            lyrics = []
                            for div in lyrics_divs:
                                lyrics.append(div.get_text(separator='\n'))
                            return '\n'.join(lyrics)
            except Exception as e:
                print(f"Scraping error: {e}")
        
        return None
    
    @staticmethod
    def paginate_lyrics(lyrics: str, lines_per_page: int = 30) -> list:
        """Paginate lyrics for display"""
        lines = lyrics.split('\n')
        pages = []
        
        for i in range(0, len(lines), lines_per_page):
            page = '\n'.join(lines[i:i + lines_per_page])
            if page.strip():
                pages.append(page)
        
        return pages if pages else ['No lyrics available']
