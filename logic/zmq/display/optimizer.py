import traceback
from .. client.QudiControl import QudiClient, BgTask
import logging

import ipywidgets as widgets
from ipywidgets import AppLayout, Layout
import asyncio
import IPython.display

import numpy as np
import matplotlib
import matplotlib.pyplot as plt


# this object represents a handle to this instance of refocusing
class Refocus:

    log = logging.getLogger('client.optimizer')

    def __init__(self, client, poi=None, lazy=False, goto=True):

        self.client = client
        self.poi = poi
        self.goto = goto
        self.plot_area = widgets.Output()
        self.cancel_area = widgets.Output()
        self.layout = AppLayout(center=self.plot_area, right_sidebase=self.cancel_area, pane_widths=[2, 4, 1])
        IPython.display.display(self.layout)

        if lazy:
            # just request the current data and display
            self.log.debug("Fetching latest optimization")
            self.bg_task = BgTask(self._fetch())
        else:
            # start the optimizer and display the result
            self.log.debug("Refocusing")
            self.bg_task = BgTask(self._refocus())
            self.layout.right_sidebar = self.bg_task.cancel_button

    async def _goto_current(self):
        try:
            await self.client.send_command('goto_current')
        except Exception as e:
            self.log.error("'Goto current' exception: {}".format(e))

    async def _fetch(self):
        try:
            self.log.debug("Pushdata")
            await self.client.send_command('pushdata')
            self.log.debug("wait")
            await self._display()
        except Exception as e:
            self.log.error("Fetch exception: {}".format(e))

    async def _refocus(self):
        try:
            if self.poi:
                await self.client.send_command('refocus', body={'poi': self.poi})
            else:
                await self.client.send_command('refocus', body='')
            await self._display()
            if self.goto:
                await self._goto_current()
        except Exception as e:
            self.log.error("Fetch exception: {}".format(e))

    async def _wait_for_refocus(self):
        # in the background, wait for the process to finish
        # don't block by default here
        s = self.client.subscribe('optimizer.refocused')
        self.position = await s.receive()
        return self.position

    # blocking wait on optimizer finishing
    async def wait_until_done(self):
        if self.position:
            return self.position
        else:
            return await self._wait_for_refocus()

    async def _display(self):
        s = self.client.subscribe('optimizer.data')
        data = await s.receive()
        self.result = data.body
        self.position = (self.result['x'], self.result['y'], self.result['z'])
        self.log.debug("Displaying optimizer data: {}".format(self.position))
        if 'xy_counts' in data.body:
            with self.plot_area:
                fig, axs = plt.subplots(nrows=1, ncols=2)
                xy = data.body['xy_counts']
                img = xy[:, :, 3]
                axs[0].imshow(img, cmap='inferno')
                axs[0].set_xlabel(r'X ($\mu m$)')
                axs[0].set_ylabel(r'Y ($\mu m$)')
                axs[0].set_xlim(xy[0, 0, 0])
                axs[1].scatter(data.body['z_position'], data.body['z_counts'], marker='x')
                axs[1].plot(data.body['z_fit_position'], data.body['z_fit'], linestyle='--')
                plt.show(fig)
                self.fig = fig
                self.axs = axs


#################################################

from ..client.QudiControl import QudiClient, BgTask
import logging
import traceback
 
import ipywidgets as widgets
from ipywidgets import AppLayout, Layout
import asyncio
import IPython.display
 
import numpy as np
import matplotlib
import matplotlib.pyplot as plt


# this object represents a handle to this instance of refocusing
class Refocus:

    log = logging.getLogger('client.optimizer')

    def __init__(self, client, poi=None, lazy=False, goto=True):

        self.client = client
        self.poi = poi
        self.goto = goto
        self.plot_area = widgets.Output()
        self.cancel_area = widgets.Output()
        self.layout = AppLayout(center=self.plot_area, right_sidebase=self.cancel_area, pane_widths=[2, 4, 1])
        IPython.display.display(self.layout)

        if lazy:
            # just request the current data and display
            self.log.debug("Fetching latest optimization")
            self.bg_task = BgTask(self._fetch())
        else:
            # start the optimizer and display the result
            self.log.debug("Refocusing")
            self.bg_task = BgTask(self._refocus())
            self.layout.right_sidebar = self.bg_task.cancel_button

    async def _goto_current(self):
        try:
            await self.client.send_command('goto_current')
        except Exception as e:
            self.log.error("'Goto current' exception: {}".format(e))

    async def _fetch(self):
        try:
            self.log.debug("Pushdata")
            await self.client.send_command('pushdata')
            self.log.debug("wait")
            await self._display()
        except Exception as e:
            self.log.error("Fetch exception: {}".format(e))

    async def _refocus(self):
        try:
            if self.poi:
                await self.client.send_command('refocus', body={'poi': self.poi})
            else:
                await self.client.send_command('refocus', body='')
            await self._display()
            if self.goto:
                await self._goto_current()
        except Exception as e:
            self.log.error("Fetch exception: {}".format(e))

    async def _wait_for_refocus(self):
        # in the background, wait for the process to finish
        # don't block by default here
        s = self.client.subscribe('optimizer.refocused')
        self.position = await s.receive()
        return self.position

    # blocking wait on optimizer finishing
    async def wait_until_done(self):
        if self.position:
            return self.position
        else:
            return await self._wait_for_refocus()

    async def _display(self):
        s = self.client.subscribe('optimizer.data')
        data = await s.receive()
        self.result = data.body
        self.position = (self.result['x'], self.result['y'], self.result['z'])
        self.log.debug("Displaying optimizer data: {}".format(self.position))
        if 'xy_counts' in data.body:
            with self.plot_area:
                fig, axs = plt.subplots(nrows=1, ncols=2)
                xy = data.body['xy_counts']
                img = xy[:, :, 3]
                axs[0].imshow(img, cmap='inferno')
                axs[0].set_xlabel(r'X ($\mu m$)')
                axs[0].set_ylabel(r'Y ($\mu m$)')
                axs[0].set_xlim(xy[0, 0, 0])
                axs[1].scatter(data.body['z_position'], data.body['z_counts'], marker='x')
                axs[1].plot(data.body['z_fit_position'], data.body['z_fit'], linestyle='--')
                plt.show(fig)
                self.fig = fig
                self.axs = axs
