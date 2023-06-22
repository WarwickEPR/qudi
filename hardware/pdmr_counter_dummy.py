
import numpy as np
import time
import math

from core.module import Base
from core.connector import Connector
from core.configoption import ConfigOption
from interface.pdmr_counter_interface import PDMRCounterInterface


class PDMRCounterDummy(Base, PDMRCounterInterface):
    """ Dummy hardware class to simulate the controls for a simple PDMR.

    Example config for copy-paste:

    pdmr_counter_dummy:
        module.Class: 'pdmr_counter_dummy.PDMRCounterDummy'
        clock_frequency: 100 # in Hz
        number_of_channels: 2
        fitlogic: 'fitlogic' # name of the fitlogic module, see default config

    """

    # connectors
    fitlogic = Connector(interface='FitLogic')
    picoammeterhardware = Connector(interface='PicoammeterHardware')

    # config options
    _clock_frequency = ConfigOption('clock_frequency', 100, missing='warn')
    _number_of_channels = ConfigOption('number_of_channels', 2, missing='warn')

    def __init__(self, config, **kwargs):
        super().__init__(config=config, **kwargs)

        self._scanner_counter_daq_task = None
        self._pdmr_length = None
        self._pulse_out_channel = 'dummy'
        self._lock_in_active = False
        self._oversampling = 10

    def on_activate(self):
        """ Initialisation performed during activation of the module.
        """
        self._fit_logic = self.fitlogic()
        self._picoammeter_hardware = self.picoammeterhardware()

    def on_deactivate(self):
        """ Deinitialisation performed during deactivation of the module.
        """
        self.log.debug('PDMR counter is shutting down.')

    def set_up_pdmr_clock(self, clock_frequency=None, clock_channel=None):
        """ Configures the hardware clock of the NiDAQ card to give the timing.

        @param float clock_frequency: if defined, this sets the frequency of the clock
        @param str clock_channel: if defined, this is the physical channel of the clock

        @return int: error code (0:OK, -1:error)
        """

        if clock_frequency is not None:
            self._clock_frequency = float(clock_frequency)

        self.log.info('PDMRCounterDummy>set_up_pdmr_clock')

        time.sleep(0.2)

        return 0


    def set_up_pdmr(self, counter_channel=None, photon_source=None,
                    clock_channel=None, pdmr_trigger_channel=None):
        """ Configures the actual counter with a given clock.

        @param str counter_channel: if defined, this is the physical channel of the counter
        @param str photon_source: if defined, this is the physical channel where the photons are to count from
        @param str clock_channel: if defined, this specifies the clock for the counter
        @param str pdmr_trigger_channel: if defined, this specifies the trigger output for the microwave

        @return int: error code (0:OK, -1:error)
        """

        self.log.info('PDMRCounterDummy>set_up_pdmr')

        if self.module_state() == 'locked' or self._scanner_counter_daq_task is not None:
            self.log.error('Another pdmr is already running, close this one '
                    'first.')
            return -1

        time.sleep(0.2)

        return 0

    def set_pdmr_length(self, length=100):
        """ Sets up the trigger sequence for the PDMR and the triggered microwave.

        @param int length: length of microwave sweep in pixel

        @return int: error code (0:OK, -1:error)
        """

        self._pdmr_length = length
        return 0

    def count_pdmr(self, length=100):
        """ Sweeps the microwave and returns the counts on that sweep.

        @param int length: length of microwave sweep in pixel

        @return float[]: the photon counts per second
        """

        if self.module_state() == 'locked':
            self.log.error('A scan_line is already running, close this one '
                           'first.')
            return -1

        self.module_state.lock()

        self._pdmr_length = length

        lorentians, params = self._fit_logic.make_lorentziandouble_model()

        sigma = 3.

        params.add('l0_amplitude', value=-30000)
        params.add('l0_center', value=length/3)
        params.add('l0_sigma', value=sigma)
        params.add('l1_amplitude', value=-30000)
        params.add('l1_center', value=2*length/3)
        params.add('l1_sigma', value=sigma)
        params.add('offset', value=50000.)

        ret = np.empty((self._number_of_channels, length))

        for chnl_index in range(self._number_of_channels):
            count_data = self._picoammeter_hardware.read_current()
            count_data = float(count_data.split(',')[0][:-1])
            # count_data = np.random.uniform(0, 5e4, length)
            # count_data += (chnl_index + 1) * lorentians.eval(x=np.arange(1, length + 1, 1),
            #                                                  params=params)
            ret[chnl_index] = count_data

        time.sleep(self._pdmr_length*1./self._clock_frequency)

        self.module_state.unlock()
        return False, ret


    def close_pdmr(self):
        """ Closes the pdmr and cleans up afterwards.

        @return int: error code (0:OK, -1:error)
        """

        self.log.info('PDMRCounterDummy>close_pdmr')

        self._scanner_counter_daq_task = None

        return 0

    def close_pdmr_clock(self):
        """ Closes the pdmr and cleans up afterwards.

        @return int: error code (0:OK, -1:error)
        """

        self.log.info('PDMRCounterDummy>close_pdmr_clock')

        return 0

    def get_pdmr_channels(self):
        """ Return a list of channel names.

        @return list(str): channels recorded during PDMR measurement
        """
        return ['ch{0:d}'.format(i) for i in range(1, self._number_of_channels + 1)]

    @property
    def oversampling(self):
        return self._oversampling

    @oversampling.setter
    def oversampling(self, val):
        if not isinstance(val, (int, float)):
            self.log.error('oversampling has to be int of float.')
        else:
            self._oversampling = int(val)

    @property
    def lock_in_active(self):
        return self._lock_in_active

    @lock_in_active.setter
    def lock_in_active(self, val):
        if not isinstance(val, bool):
            self.log.error('lock_in_active has to be boolean.')
        else:
            self._lock_in_active = val
            if self._lock_in_active:
                self.log.warn('Lock-In is not implemented')

