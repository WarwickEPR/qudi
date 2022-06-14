from .QudiControl import QudiClient, BgTask
import logging

import ipywidgets as widgets
from ipywidgets import AppLayout
import IPython.display

import numpy as np
import matplotlib.pyplot as plt
from IPython.display import Math, display
from scipy.optimize import curve_fit


class Psat:

    log = logging.getLogger('client.psat')

    def __init__(self, client):

        self.client = client
        self.plot_area = widgets.Output()
        self.layout = AppLayout(center=self.plot_area, pane_widths=[1, 4, 4])
        IPython.display.display(self.layout)

        # measure psat and display the result
        self.log.debug("Taking Psat")
        self.psat_data = None
        self.I_0 = 0
        self.P_sat = 0
        self.background = 0
        self.bg_task = BgTask(self._take_psat())
        self.layout.right_sidebar = self.bg_task.cancel_button

    async def _take_psat(self):
        try:
            self.I_0 = 0
            self.P_sat = 0
            self.background = 0
            self.psat_data = None
            await self.client.send_command('take_psat', body='')
            await self._display()
        except Exception as e:
            self.log.error("Fetch exception: {}".format(e))

    async def _wait_for_measurement(self):
        # in the background, wait for the process to finish
        # don't block by default here
        s = self.client.subscribe('aom.psat_data')
        response = await s.receive()
        self.layout.right_sidebar = widgets.Output(layout={'border': '1px solid black'})
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

    async def fitted(self):
        await self.done()
        self.fit_with_bg()
        return

    async def _display(self):
        data = await self.data()
        self.log.debug("Displaying psat data: {}".format(data))
        if 'counts' in data:
            with self.plot_area:
                I_0, P_sat, bg = self.fit_with_bg()
                P = data['powers']*1e3
                plt.scatter(P, data['counts']*1e-3, P)
                plt.plot(P, Psat._model_with_bg(P, I_0, P_sat, bg)*1e-3)
                plt.xlabel(r'Power (mW)', fontsize=18)
                plt.ylabel(r'Count rate (kc/s)', fontsize=18)
                plt.grid()
                plt.show()
            with self.layout.right_sidebar:
                display(Math('I_0 = {:.1f}~kc/s'.format(I_0*1e-3)))
                display(Math('P_{{sat}} = {:.2f}~mW'.format(P_sat)))
                display(Math('background = {:.1f}~kc/s/mW'.format(bg*1e-3)))

    @classmethod
    def _model_simple(cls, p, I_0, P_sat):
        return I_0 * p / (p + P_sat)

    @classmethod
    def _model_with_bg(cls, p, I_0, P_sat, bg):
        return I_0 * p / (p + P_sat) + bg * p

    def fit_simple(self):
        pars, cov = curve_fit(Psat._model_simple, self.psat_data['powers']*1e3, self.psat_data['counts'], p0=[100e3, 1], bounds=(0, np.inf))
        self.I_0 = pars[0]
        self.P_sat = pars[1]
        return self.I_0, self.P_sat

    def fit_with_bg(self):
        I_max = np.max(self.psat_data['counts'])
        pars, cov = curve_fit(Psat._model_with_bg, self.psat_data['powers']*1e3, self.psat_data['counts'], p0=[I_max, 1, 0], bounds=([I_max*.5, 0, 0], [np.inf, np.inf, np.inf]))
        self.I_0 = pars[0]
        self.P_sat = pars[1]
        self.background = pars[2]
        return self.I_0, self.P_sat, self.background


class Aom(QudiClient):

    name = "aom"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def take_psat(self):
        return Psat(self)

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

    async def save_qudi(self, tag=''):
        if tag != '':
            await self.send_command('save_qudi', tag)
        else:
            await self.send_command('save_qudi')

    async def set_power(self, power):
        await self.send_command('set_power', body=power)

    async def get_power(self):
        await self.send_command('get_power')
        msg = await self.receive_message()
        power = msg.body
        return power
