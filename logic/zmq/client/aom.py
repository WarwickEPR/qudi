from .QudiControl import QudiClient, BgTask
import logging

import ipywidgets as widgets
from ipywidgets import AppLayout
import IPython.display

import matplotlib.pyplot as plt


class Psat:

    log = logging.getLogger('client.psat')

    def __init__(self, client):

        self.client = client
        self.plot_area = widgets.Output()
        self.cancel_area = widgets.Output()
        self.layout = AppLayout(center=self.plot_area, right_sidebase=self.cancel_area, pane_widths=[2, 4, 1])
        IPython.display.display(self.layout)

        # measure psat and display the result
        self.log.debug("Taking Psat")
        self.psat_data = None
        self.bg_task = BgTask(self._take_psat())
        self.layout.right_sidebar = self.bg_task.cancel_button

    async def _take_psat(self):
        try:
            await self.client.send_command('take_psat', body='')
            await self._display()
        except Exception as e:
            self.log.error("Fetch exception: {}".format(e))

    async def _wait_for_measurement(self):
        # in the background, wait for the process to finish
        # don't block by default here
        s = self.client.subscribe('aom.psat_data')
        response = await s.receive()
        self.psat_data = response.body
        return self.psat_data

    # blocking wait on data collection, returns data
    async def data(self):
        if self.psat_data:
            return self.psat_data
        else:
            return await self._wait_for_measurement()

    # blocking wait on collection, but discards
    async def done(self):
        await self.data()

    async def _display(self):
        data = await self.data()
        self.log.debug("Displaying psat data: {}".format(data))
        if 'counts' in data:
            with self.plot_area:
                plt.scatter(data['powers']*1e3, data['counts'])
                plt.xlabel(r'Power (mW)')
                plt.ylabel(r'Count rate (c/s)')
                plt.show()


class Aom(QudiClient):

    name = "aom"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def take_psat(self):
        return Psat(self)
        # await self.send_command('take_psat')

    async def wait_for_psat_fit(self):
        s = self.subscribe('aom.fit')
        response = await s.receive()
        return response.body

    async def wait_for_psat_data(self):
        s = self.subscribe('aom.data')
        response = await s.receive()
        return response.body

    async def emit_psat(self):
        await self.send_command('emit')

    async def save(self):
        await self.send_command('save')

    async def save_hdf(self):
        await self.send_command('save_hdf')

    async def set_power(self, power):
        await self.send_command('set_power', body=power)

    async def get_power(self):
        await self.send_command('get_power')
        msg = await self.receive_message()
        power = msg.body
        return power
