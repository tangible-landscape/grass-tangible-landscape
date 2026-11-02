"""Detects when the GUI/asyncio event loop is blocked.

The wx GUI, the asyncio loop with the dashboard websocket and all
synchronous GRASS and HTTP calls share one thread. When that thread
is busy for longer than the server's ping timeout, the websocket is
closed. This monitor prints where the thread is stuck so that such
places can be found and moved to a worker thread.
"""

import asyncio
import sys
import threading
import time
import traceback


class StallMonitor:
    def __init__(self, threshold=5.0, prefix="dashboard"):
        self.threshold = threshold
        self.prefix = prefix
        self._task = None
        self._thread = None
        self._loop_thread_id = None
        self._last_tick = None
        self._stop = threading.Event()

    def start(self):
        """Call from the thread running the asyncio loop"""
        if self._task is not None:
            return
        self._loop_thread_id = threading.get_ident()
        self._last_tick = time.monotonic()
        self._stop.clear()
        self._task = asyncio.ensure_future(self._tick())
        self._thread = threading.Thread(target=self._watch, daemon=True)
        self._thread.start()

    def stop(self):
        self._stop.set()
        if self._task is not None:
            self._task.cancel()
            self._task = None

    async def _tick(self):
        while True:
            self._last_tick = time.monotonic()
            await asyncio.sleep(0.5)

    def _format_stack(self):
        frame = sys._current_frames().get(self._loop_thread_id)
        if frame is None:
            return "  (stack not available)"
        return "".join(traceback.format_stack(frame))

    def _watch(self):
        stall_start = None
        last_report = None
        while not self._stop.wait(1.0):
            now = time.monotonic()
            lag = now - self._last_tick
            if lag > self.threshold:
                if stall_start is None:
                    stall_start = self._last_tick
                # report at the start and then every 20 s while it lasts,
                # the stack may have moved on
                if last_report is None or now - last_report > 20:
                    last_report = now
                    print(
                        f"{self.prefix}: event loop blocked for {lag:.0f} s, "
                        f"GUI thread is in:\n{self._format_stack()}",
                        flush=True,
                    )
            elif stall_start is not None:
                print(
                    f"{self.prefix}: event loop unblocked after "
                    f"{now - stall_start:.0f} s",
                    flush=True,
                )
                stall_start = last_report = None
