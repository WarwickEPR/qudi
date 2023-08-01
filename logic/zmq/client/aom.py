from .QudiControl import QudiClient, BgTask
import logging

import ipywidgets as widgets
from ipywidgets import AppLayout
import IPython.display

import numpy as np
import matplotlib.pyplot as plt
from IPython.display import Math, display
from scipy.optimize import curve_fit, OptimizeWarning


class Psat:

    log = logging.getLogger('client.psat')

    def __init__(self, client):

        self.client = client

        # measure psat and display the result
        self.log.debug("Taking Psat")
        self.psat_data = {'powers': np.array([]), 'counts': np.array([])}
        self.I_0 = 0
        self.P_sat = 0
        self.fit_covariance = None
        self.background = 0

        # in case we want to cancel, start immediately and wait in the background
        self.bg_task = BgTask(self._take_psat())

    async def _take_psat(self):
        try:
            self.I_0 = 0
            self.P_sat = 0
            self.background = 0
            self.psat_data = None
            await self.client.send_command('take_psat', body='')
            await self._wait_for_measurement()
            self.log.debug("Received psat data: {}".format(self.psat_data))
        except Exception as e:
            self.log.error("Fetch exception: {}".format(e))

    async def _wait_for_measurement(self):
        # in the background, wait for the process to finish
        # don't block by default here
        s = self.client.subscribe('aom.psat_data')
        response = await s.receive()
        self.psat_data = response.body

    # blocking wait on data collection, returns data
    async def data(self):
        if not self.psat_data:
            await self._wait_for_measurement()
        return self.psat_data

    # blocking wait on collection, but discards
    async def done(self):
        await self.data()

    async def fitted(self):
        await self.done()
        self.fit_with_bg()
        return

    @classmethod
    def _model_simple(cls, p, I_0, P_sat):
        return I_0 * p / (p + P_sat)

    @classmethod
    def _model_with_bg(cls, p, I_0, P_sat, bg):
        return I_0 * p / (p + P_sat) + bg * p

    def fit_simple(self):
        powers = self.psat_data['powers']*1e3
        counts = self.psat_data['counts']
        try:
            pars, cov = curve_fit(f=Psat._model_simple, xdata=powers, ydata=counts, p0=[100e3, 1], bounds=(0, np.inf))
            self.I_0 = pars[0]
            self.P_sat = pars[1]
            self.fit_covariance = cov
        except ValueError:
            self.log.warning('AOM fit - data contained NaN')
        except RuntimeError:
            self.log.warning('AOM fit failed')
        except OptimizeWarning:
            self.log.warning('AOM fit - covariance could not be calculated')

        return self.I_0, self.P_sat

    def fit_with_bg(self):
        powers = self.psat_data['powers']*1e3
        counts = self.psat_data['counts']
        if not len(counts):
            self.log.warning("No Psat data returned")
            return 0, 0, 0
        I_max = np.max(counts)
        try:
            pars, cov = curve_fit(f=Psat._model_with_bg, xdata=powers, ydata=counts, p0=[I_max, 1, 0], bounds=([I_max*.5, 0, 0], [np.inf, np.inf, np.inf]))
            self.I_0 = pars[0]
            self.P_sat = pars[1]
            self.background = pars[2]
            self.fit_covariance = cov
        except ValueError:
            self.log.warning('AOM fit - data contained NaN')
        except RuntimeError:
            self.log.warning('AOM fit failed')
        except OptimizeWarning:
            self.log.warning('AOM fit - covariance could not be calculated')

        return self.I_0, self.P_sat, self.background

    def display(self):
        P = self.psat_data['powers']
        plt.scatter(P, self.psat_data['counts'])
        plt.plot(P, self._model_with_bg(P, self.I_0, self.P_sat, self.background), color='blue')
        plt.xlabel('Power (mW)',fontsize=18)
        plt.ylabel('Counts', fontsize=18)
        plt.grid()
        plt.title('Psat', fontsize=18)
        plt.show()

class Aom(QudiClient):

    name = "aom"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def take_psat(self):
        return Psat(self)

    def display_psat(self):
        pass

    async def _display_psat(self):
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

    async def save(self, tag=''):
        await self.send_command('save', tag)

    async def save_qudi(self, tag=''):
        await self.send_command('save_qudi', tag)

    async def set_power(self, power):
        await self.send_command('set_power', body=power)

    async def get_power(self):
        await self.send_command('get_power')
        msg = await self.receive_message()
        power = msg.body
        return power
