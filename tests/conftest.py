"""
Conftest - Pytest configuration
"""
import pytest
import asyncio
import pytest_asyncio
from src.queue import Queue, Track


@pytest.fixture
def event_loop():
    """Create event loop for async tests"""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    yield loop
    if not loop.is_closed():
        loop.close()


@pytest_asyncio.fixture
async def empty_queue():
    """Create empty queue fixture"""
    return Queue()


@pytest_asyncio.fixture
async def queue_with_tracks():
    """Create queue with sample tracks"""
    queue = Queue()
    tracks = [
        Track(
            title="Song 1",
            url="https://example.com/1",
            duration=180,
            source="youtube",
            artist="Artist 1",
            added_by_name="User1"
        ),
        Track(
            title="Song 2",
            url="https://example.com/2",
            duration=240,
            source="spotify",
            artist="Artist 2",
            added_by_name="User2"
        ),
        Track(
            title="Song 3",
            url="https://example.com/3",
            duration=200,
            source="youtube",
            artist="Artist 3",
            added_by_name="User3"
        ),
    ]
    
    for track in tracks:
        await queue.add(track)
    
    return queue
