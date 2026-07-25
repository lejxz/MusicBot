"""
Lightweight playback diagnostics — counters + grep-able event log.

Measures the two confirmed dropout causes (voice-WS disconnects, mid-stream
403s) plus playback gaps, without a custom AudioSource or any new dependency.

ponytail: module-level singleton, plain ints under the GIL. No lock — every
writer is either the event loop or discord.py's player thread doing atomic
int += 1 / list.append, which the GIL serializes. Upgrade to a Lock only if a
counter ever looks torn (it won't at this event rate).

Every record() bumps a counter AND emits one structured line:
    METRIC event=<name> k=v k=v ...
so `grep METRIC logs/bot.log` gives a full history with zero live monitoring.
"""
import time
import logging
from collections import deque

logger = logging.getLogger("src.metrics")

_START = time.monotonic()

counters = {
    "tracks_started": 0,
    "tracks_finished_ok": 0,
    "tracks_errored": 0,
    "voice_disconnects": 0,
    "stream_403s": 0,
    "playback_gaps": 0,
}

# extra scalar state (not simple monotonic counters)
state = {
    "voice_reconnect_total_wait_s": 0.0,
    "longest_reconnect_wait_s": 0.0,
    "last_disconnect_ts": None,  # monotonic seconds
}

# recent events for /stats (bounded — no unbounded growth)
recent = deque(maxlen=20)


def record(event: str, **fields) -> None:
    """Bump the matching counter, update state, log one grep line, keep in ring."""
    if event == "track_start":
        counters["tracks_started"] += 1
    elif event == "track_ok":
        counters["tracks_finished_ok"] += 1
    elif event == "track_error":
        counters["tracks_errored"] += 1
    elif event == "voice_disconnect":
        counters["voice_disconnects"] += 1
        wait = float(fields.get("wait", 0.0) or 0.0)
        state["voice_reconnect_total_wait_s"] += wait
        if wait > state["longest_reconnect_wait_s"]:
            state["longest_reconnect_wait_s"] = wait
        state["last_disconnect_ts"] = time.monotonic()
    elif event == "stream_403":
        counters["stream_403s"] += 1
    elif event == "playback_gap":
        counters["playback_gaps"] += 1

    kv = " ".join(f"{k}={v}" for k, v in fields.items())
    logger.info("METRIC event=%s %s", event, kv)
    recent.append((round(time.monotonic() - _START, 1), event, fields))


def uptime_s() -> float:
    return time.monotonic() - _START


def snapshot() -> dict:
    """Flat dict for /stats rendering."""
    return {
        "uptime_s": uptime_s(),
        **counters,
        **state,
        "recent": list(recent),
    }
