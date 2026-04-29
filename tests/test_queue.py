"""
Test suite for Queue module
"""
import pytest
from src.queue import Queue, Track


@pytest.mark.asyncio
async def test_add_track(empty_queue):
    """Test adding track to queue"""
    track = Track(
        title="Test Track",
        url="https://example.com/test",
        duration=180,
        source="youtube",
        artist="Test Artist"
    )
    
    await empty_queue.add(track)
    assert len(await empty_queue.get_all()) == 1


@pytest.mark.asyncio
async def test_remove_track(queue_with_tracks):
    """Test removing track from queue"""
    initial_size = await queue_with_tracks.size()
    removed = await queue_with_tracks.remove(0)
    
    assert removed is not None
    assert len(await queue_with_tracks.get_all()) == initial_size - 1


@pytest.mark.asyncio
async def test_clear_queue(queue_with_tracks):
    """Test clearing entire queue"""
    await queue_with_tracks.clear()
    assert await queue_with_tracks.size() == 0


@pytest.mark.asyncio
async def test_shuffle_queue(queue_with_tracks):
    """Test shuffling queue"""
    original = [t.title for t in await queue_with_tracks.get_all()]
    await queue_with_tracks.shuffle()
    shuffled = [t.title for t in await queue_with_tracks.get_all()]
    
    # Check that all tracks are still there
    assert sorted(original) == sorted(shuffled)


@pytest.mark.asyncio
async def test_move_track(queue_with_tracks):
    """Test moving track in queue"""
    success = await queue_with_tracks.move(0, 2)
    assert success is True


@pytest.mark.asyncio
async def test_toggle_loop(queue_with_tracks):
    """Test loop mode toggling"""
    mode = queue_with_tracks.toggle_loop()
    assert mode == 1
    
    mode = queue_with_tracks.toggle_loop()
    assert mode == 2
    
    mode = queue_with_tracks.toggle_loop()
    assert mode == 0


@pytest.mark.asyncio
async def test_queue_info(queue_with_tracks):
    """Test getting queue info"""
    info = await queue_with_tracks.get_queue_info()
    
    assert "total_tracks" in info
    assert "total_duration" in info
    assert info["total_tracks"] == 3
    assert info["total_duration"] == 620  # 180 + 240 + 200
