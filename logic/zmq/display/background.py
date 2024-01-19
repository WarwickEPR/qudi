import datetime
import threading
import time
import math
import asyncio
import logging

import ipywidgets as widgets
from ipywidgets import Layout


# holder for a running background Task and an associated cancellation button
class BgTask:

    log = logging.getLogger('core.bg')

    def __init__(self, coroutine, on_done=None, on_cancel=None):
        self.log.debug("Scheduling coroutine {} as task".format(coroutine))

        self.progress = widgets.FloatProgress(value=0,
                                              description="",
                                              min=0.0,
                                              max=100.0,
                                              orientation='horizontal',
                                              bar_style='',
                                              layout=Layout(width='500px'))

        async def wrapped_coroutine():
            try:
                await coroutine
                if on_done:
                    await on_done
            except asyncio.CancelledError as e:
                if on_cancel is not None:
                    await on_cancel

        self._coroutine = wrapped_coroutine()
        self.task = None
        self._update_task = None

    def start(self):
        self.setup_progress_bar()
        self.task = asyncio.create_task(self._coroutine)
        self._update_task = asyncio.create_task(self._progress_loop())

    async def _progress_loop(self):
        while not self.task.done():
            self.update_progress()
            await asyncio.sleep(0.5)

    def cancel(self):
        self.log.warning("Cancelling")
        self.task.cancel()
        self._update_task.cancel()
        self.progress.description = "Cancelled"

    def cancel_button(self):
        cancel_button = widgets.Button(description='',
                                       disabled=False,
                                       button_style='',
                                       tooltip='Stop',
                                       icon='window-close')
        cancel_button.style.button_color = 'transparent'

        def cancel(btn):
            self.cancel()
            self.cancel_button.disabled = True

        cancel_button.on_click(cancel)
        return cancel_button

    def cancel_button_right(self, out):
        return widgets.HBox(children=[out, self.cancel_button()],
                            layout=widgets.Layout(display='flex', justify_content='space-between'))

    def update_progress(self):
        self.progress.description = ''
        self.progress.value = 0

    def setup_progress_bar(self):
        pass

    def display_progress(self):
        return widgets.HBox(children=[self.progress, self.cancel_button()],
                            layout=widgets.Layout(display='flex', justify_content='space-between'))

    async def done(self):
        try:
            await self.task
        except asyncio.CancelledError:
            self.log.warning("Cancelled")


class BgWait(BgTask):
    # Specialisation of BgTask just to pause for duration seconds
    def __init__(self, duration, after_wait=None):
        async def sleep():
            t = duration
            while t > 1:
                self.log.debug("T: {}".format(t))
                await asyncio.sleep(1)
                t = t - 1
            await asyncio.sleep(t)

        super().__init__(asyncio.sleep(duration), after_wait)
        self._duration = duration
        self._start_time = time.time()
        self._end_time = self._start_time + self._duration

    def time_remaining(self):
        remaining = self._end_time - time.time()
        if remaining < 0:
            remaining = 0
        return remaining

    def time_elapsed(self):
        return time.time() - self._start_time

    @classmethod
    def seconds_to_string(cls, secs):
        return str(datetime.timedelta(seconds=math.floor(secs)))

    def progress_str(self):
        return '{} remaining of {}'.format(self.seconds_to_string(self.time_remaining()),
                                           self.seconds_to_string(self._duration))

    def update_progress(self):
        self.progress.description = self.progress_str()
        self.progress.value = self.time_remaining()

    def setup_progress_bar(self):
        self.progress.min = 0.0
        self.progress.max = self._duration
        self.update_progress()
