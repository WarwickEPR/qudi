import asyncio
import logging

from . track import Track
import time
import os.path
import os

# Cancelling long running IPython sub-notebooks requires a way to tell the notebook to stop "out of band"
# and allow for clean up
# InterruptKernel would be nice but can't be caught in the user code (at least on Windows)
# Bidirectional comm communication or a shell command would also be a possibility but not exposed nicely in ipykernel
# Using the Qudi ZMQ comms adds another dependency on Qudi running so resort to watching a file
# Doesn't need to be fast, just allow interrupting long waits to get to the end of the cell would do


class InterruptableWaitManager:

    def __init__(self, stop_file='.stop', tracker=None):
        self._stop_file = stop_file
        self._tracker: Track = tracker
        self._iw = set()
        self._cancelled = False
        self._logger = logging.getLogger('WaitManager')

        if self._tracker:
            # Let the parent notebook know where to put a stop file to trigger cancellation
            self._tracker.send_stop_file(self._stop_file)

        # check stop file is not there when we start
        if os.path.exists(self._stop_file):
            try:
                os.remove(self._stop_file)
            except OSError as e:
                self._logger.error("Failed to remove stop file: {}".format(e))

        self.poll_task = asyncio.create_task(self._poll_stop_file(), name='stop_poll')

    def clear(self):
        self._cancelled = True
        if self.poll_task:
            self.poll_task.cancel()
        self.poll_task = None

    async def wait_for(self, aw, condition_description='', timeout=None):
        wait_task = asyncio.create_task(aw, name='wait-<{}>'.format(condition_description))
        emit_task = asyncio.create_task(self._emit_waiting(condition_description), name='wait-emit-<{}>'.format(condition_description))
        self._iw.add(wait_task)
        wait_task.add_done_callback(lambda _: self._iw.discard(wait_task))
        aws = [wait_task, emit_task]

        try:
            done, pending = await asyncio.wait(aws, timeout=timeout, return_when=asyncio.FIRST_COMPLETED)
        except asyncio.CancelledError:
            pass

        emit_task.cancel()
        return wait_task.result()

    async def _poll_stop_file(self):
        while not self._cancelled:
            # check for stop file creation
            if os.path.exists(self._stop_file):
                # remove file
                os.remove(self._stop_file)
                # cancel all wait tasks (probably just one!)
                for iw in self._iw:
                    iw.cancel()
            await asyncio.sleep(1)

    @staticmethod
    def _format_wait(t):
        hours = int(int(t) / (60 * 60))
        mins = int(int(t) % (60 * 60) / 60)
        seconds = int(t) % 60
        return "{}h{}m{}s".format(hours, mins, seconds)

    async def _emit_waiting(self, condition, interval=1):
        start_time = time.time()
        while not self._cancelled:
            waited_time = time.time() - start_time
            self._tracker.progress("Waiting for <{}> for {}".format(condition, self._format_wait(waited_time)))
            await asyncio.sleep(interval)


class InterruptableWaitHandle:
    def __init__(self):
        self.stopped = False
        self._stop_file = None

    def set_stop_file(self, stop_file: str):
        self._stop_file = stop_file

    def stop(self):
        self.stopped = True
        if self._stop_file:
            # touch file
            with open(self._stop_file, 'w'):
                pass
