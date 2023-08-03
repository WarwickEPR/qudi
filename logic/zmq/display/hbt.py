
from ..client.QudiControl import BgTask
import logging

import ipywidgets as widgets
from ipywidgets import AppLayout
import IPython.display
import asyncio

import numpy as np
import matplotlib.pyplot as plt
from IPython.display import Math, display
from scipy.optimize import curve_fit


class HbtMeasurement:

    log = logging.getLogger('client.hbt')

    def __init__(self, client):

        self.client = client
        self.plot_area = widgets.Output()
        self.layout = AppLayout(center=self.plot_area, pane_widths=[1, 4, 4])
        IPython.display.display(self.layout)

        self.log.debug("Taking Hbt")
        self.hbt_data = None
        self._bg_task = BgTask(self._take_hbt())
        self._bg_update = asyncio.create_task(self._update)
        self.layout.right_sidebar = self._bg_task.cancel_button

    async def start(self):
        try:
            self.hbt_data = None
            await self.client.send_command('start', body='')
            await self._display()
        except Exception as e:
            self.log.error("Exception: {}".format(e))

    async def stop(self):
        try:
            await self.client.send_command('stop', body='')
            await self._display()
        except Exception as e:
            self.log.error("Exception: {}".format(e))

    async def _take_hbt(self, duration=120):
        try:
            await self.start()
            await asyncio.sleep(duration)
            await self.stop()
        except Exception as e:
            self.log.error("Exception taking HBT {}".format(e))

    async def _wait_for_stop(self):
        # in the background, wait for the measurement to be stopped
        # don't block by default here
        s = self.client.subscribe('hbt.stopping')
        response = await s.receive()
        self.layout.right_sidebar = widgets.Output(layout={'border': '1px solid black'})

    async def _update(self):
        s = self.client.subscribe('hbt.data')
        response = await s.receive()
        self.hbt_data = response.body
        return self.hbt_data

    # blocking wait on data collection, returns data
    async def data(self):
        if self.hbt_data:
            return self.hbt_data
        else:
            return await self._wait_for_measurement()

    # blocking wait on collection, but discards
    async def done(self):
        await self.data()

    async def _display(self):
        data = await self.data()
        self.log.debug("Displaying HBT data: {}".format(data))
        if 'counts' in data:
            with self.plot_area:
                t = data['bin_times']*1e9
                plt.scatter(t, data['g2_data_normalized'])
                plt.xlabel(r'Time (ns)', fontsize=18)
                plt.ylabel(r'g2 normalized', fontsize=18)
                plt.grid()
                plt.show()

    def display(self):
        data = self.hbt_data
        self.log.debug("Displaying HBT data: {}".format(data))
        if 'counts' in data:
            t = data['bin_times']*1e9
            plt.scatter(t, data['g2_data_normalized'])
            plt.xlabel(r'Time (ns)', fontsize=18)
            plt.ylabel(r'g2 normalized', fontsize=18)
            plt.title('HBT', fontsize=18)
            plt.grid()
            plt.show()