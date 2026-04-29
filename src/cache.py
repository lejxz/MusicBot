"""
Local audio cache system
"""
import asyncio
import hashlib
import aiohttp
from pathlib import Path
from typing import Optional
from config import Config


class AudioCache:
    """Manages local audio caching"""
    
    def __init__(self, cache_dir: Path = None):
        self.cache_dir = cache_dir or Config.CACHE_DIR
        self.cache_dir.mkdir(exist_ok=True, parents=True)
        self._downloading = set()
    
    def _get_cache_path(self, url: str) -> Path:
        """Generate cache file path from URL"""
        url_hash = hashlib.md5(url.encode()).hexdigest()
        return self.cache_dir / f"{url_hash}.mp3"
    
    async def get_cached(self, url: str) -> Optional[str]:
        """Get cached audio file path if exists"""
        cache_path = self._get_cache_path(url)
        
        if cache_path.exists():
            return str(cache_path)
        
        return None
    
    async def cache_audio(self, url: str, stream_url: str) -> Optional[str]:
        """Download and cache audio file"""
        cache_path = self._get_cache_path(url)
        
        # Return if already cached
        if cache_path.exists():
            return str(cache_path)
        
        # Prevent duplicate downloads
        if url in self._downloading:
            # Wait for download to complete
            while url in self._downloading:
                await asyncio.sleep(0.5)
            if cache_path.exists():
                return str(cache_path)
            return None
        
        try:
            self._downloading.add(url)
            
            async with aiohttp.ClientSession() as session:
                async with session.get(stream_url, timeout=aiohttp.ClientTimeout(total=300)) as resp:
                    if resp.status == 200:
                        # Write to cache
                        with open(cache_path, 'wb') as f:
                            async for chunk in resp.content.iter_chunked(8192):
                                f.write(chunk)
                        
                        return str(cache_path)
        except Exception as e:
            print(f"Cache error for {url}: {e}")
            if cache_path.exists():
                cache_path.unlink()
        finally:
            self._downloading.discard(url)
        
        return None
    
    async def clear_old_cache(self, max_age_days: int = 7) -> int:
        """Remove cache files older than max_age_days"""
        import time
        
        current_time = time.time()
        removed_count = 0
        max_age_seconds = max_age_days * 24 * 3600
        
        for cache_file in self.cache_dir.glob("*.mp3"):
            file_age = current_time - cache_file.stat().st_mtime
            
            if file_age > max_age_seconds:
                try:
                    cache_file.unlink()
                    removed_count += 1
                except Exception as e:
                    print(f"Error removing cache file {cache_file}: {e}")
        
        return removed_count

    async def clear_all_cache(self) -> int:
        """Remove all cache files and return count removed"""
        removed_count = 0

        for cache_file in self.cache_dir.glob("*.mp3"):
            try:
                cache_file.unlink()
                removed_count += 1
            except Exception as e:
                print(f"Error removing cache file {cache_file}: {e}")

        return removed_count
    
    async def get_cache_size(self) -> int:
        """Get total cache size in bytes"""
        total_size = 0
        
        for cache_file in self.cache_dir.glob("*.mp3"):
            try:
                total_size += cache_file.stat().st_size
            except Exception:
                pass
        
        return total_size
