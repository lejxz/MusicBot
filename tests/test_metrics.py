"""Self-check for src.metrics — run: python tests/test_metrics.py"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import metrics


def test_counters_and_state():
    base = dict(metrics.counters)

    metrics.record("track_start", dur=100)
    assert metrics.counters["tracks_started"] == base["tracks_started"] + 1

    metrics.record("voice_disconnect", wait=12.5)
    metrics.record("voice_disconnect", wait=230.6)
    assert metrics.counters["voice_disconnects"] == base["voice_disconnects"] + 2
    assert metrics.state["longest_reconnect_wait_s"] >= 230.6
    assert metrics.state["voice_reconnect_total_wait_s"] >= 243.1

    metrics.record("stream_403")
    metrics.record("playback_gap", expected=100, actual=40)
    assert metrics.counters["stream_403s"] == base["stream_403s"] + 1
    assert metrics.counters["playback_gaps"] == base["playback_gaps"] + 1

    snap = metrics.snapshot()
    assert "uptime_s" in snap and snap["uptime_s"] >= 0
    assert len(snap["recent"]) >= 5  # ring holds recent events


if __name__ == "__main__":
    test_counters_and_state()
    print("ok")
