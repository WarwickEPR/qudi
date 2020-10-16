# -*- coding: utf-8 -*-

"""
This file contains the hardware file for the MOGLabs MWM economical wavemeter.
Designed to take measurements from the mogwave TCP/IP server, rather than having
to deal with communication to the hardware itself.

Qudi is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

Qudi is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with Qudi. If not, see <http://www.gnu.org/licenses/>.

Copyright (c) the Qudi Developers. See the COPYRIGHT.txt file at the
top-level directory of this distribution and at <https://github.com/Ulm-IQO/qudi/>
"""

from qtpy import QtCore
from interface.wavemeter_interface import WavemeterInterface
from core.module import Base
from core.configoption import ConfigOption
from core.util.mutex import Mutex
from hardware.mogdevice import MOGDevice

class HardwarePull(QtCore.QObject):
    """ Helper class for running the hardware communication in a separate thread. """

    # signal to deliver the wavelength to the parent class
    sig_wavelength = QtCore.Signal(float)

    def __init__(self, parentclass):
        super().__init__()

        # remember the reference to the parent class to access functions ad settings
        self._parentclass = parentclass


    def handle_timer(self, state_change):
        """ Threaded method that can be called by a signal from outside to start the timer.

        @param bool state: (True) starts timer, (False) stops it.
        """

        if state_change:
            self.timer = QtCore.QTimer()
            self.timer.timeout.connect(self._measure_thread)
            self.timer.start(self._parentclass._measurement_timing)
        else:
            if hasattr(self, 'timer'):
                self.timer.stop()

    def _measure_thread(self):
        """ The threaded method querying the data from the wavemeter.
        """

        # update as long as the state is busy
        if self._parentclass.module_state() == 'running':
            # get the current wavelength from the wavemeter

            temp=self._parentclass.get_wavelength()

            # send the data to the parent via a signal
            self.sig_wavelength.emit(temp)

class MOGLabsMWMWavemeter(Base,WavemeterInterface):
    """ Hardware class to controls a MOGLabs MWM wavemeter.

    Example config for copy-paste:

    moglabs_wavemeter:
        module.Class: 'moglabs_mwm.MOGLABsMWMWavemeter'
        measurement_timing: 10.0 # in seconds
    """

    # config options
    _measurement_timing = ConfigOption('measurement_timing', default=10.)
    _address = ConfigOption('address', default='localhost')

    # signals
    sig_handle_timer = QtCore.Signal(bool)

    def __init__(self, config, **kwargs):
        super().__init__(config=config, **kwargs)

        #locking for thread safety
        self.threadlock = Mutex()

        # the current wavelength read by the wavemeter in nm (vac)
        self._current_wavelength = 0.0

    def on_activate(self):
        #############################################
        # Initialisation to access external DLL
        #############################################
        try:
            self._dev = MOGDevice(self._address, port=7803)
        except:
            self.log.critical('Cannot connect to MOGLabs MWM wavemeter.')

        self.log.info('Connected to mogwave server with info {}'.format( self._dev.ask('info')))

        # create an independent thread for the hardware communication
        self.hardware_thread = QtCore.QThread()

        # create an object for the hardware communication and let it live on the new thread
        self._hardware_pull = HardwarePull(self)
        self._hardware_pull.moveToThread(self.hardware_thread)

        # connect the signals in and out of the threaded object
        self.sig_handle_timer.connect(self._hardware_pull.handle_timer)
        self._hardware_pull.sig_wavelength.connect(self.handle_wavelength)

        # start the event loop for the hardware
        self.hardware_thread.start()

    def on_deactivate(self):
        if self.module_state() != 'idle' and self.module_state() != 'deactivated':
            self.stop_acqusition()
        self.hardware_thread.quit()
        self.sig_handle_timer.disconnect()
        self._hardware_pull.sig_wavelength.disconnect()

        return 0

    #############################################
    # Methods of the main class
    #############################################

    def handle_wavelength(self, wavelength):
        """ Function to save the wavelength, when it comes in with a signal.
        """
        self._current_wavelength = wavelength

    def start_acqusition(self):
        """ Method to start the wavemeter software.

        @return int: error code (0:OK, -1:error)

        Also the actual threaded method for getting the current wavemeter reading is started.
        """

        # first check its status
        if self.module_state() == 'running':
            self.log.error('Wavemeter busy')
            return -1

        self.module_state.run()
        # actually start the wavemeter
        self._start_measurement() #starts measurement

        # start the measuring thread
        self.sig_handle_timer.emit(True)

        return 0

    def stop_acqusition(self):
        """ Stops the Wavemeter from measuring and kills the thread that queries the data.

        @return int: error code (0:OK, -1:error)
        """
        # check status just for a sanity check
        if self.module_state() == 'idle':
            self.log.warning('Wavemeter was already stopped, stopping it '
                    'anyway!')
        else:
            # stop the measurement thread
            self.sig_handle_timer.emit(True)
            # set status to idle again
            self.module_state.stop()

        # Stop the actual wavemeter measurement
        self._stop_measurement()

        return 0

    def get_current_wavelength(self, kind="vac"):
        """ This method returns the current wavelength.

        @param string kind: can either be "air" or "vac" for the wavelength in air or vacuum, respectively.

        @return float: wavelength (or negative value for errors)
        """
        if kind in "vac":
            # for vacuum just return the current wavelength
            return float(self._current_wavelength)
        return -2.0

    def get_timing(self):
        """ Get the timing of the internal measurement thread.

        @return float: clock length in second
        """
        return self._measurement_timing

    def set_timing(self, timing):
        """ Set the timing of the internal measurement thread.

        @param float timing: clock length in second

        @return int: error code (0:OK, -1:error)
        """
        self._measurement_timing=float(timing)
        return 0

    def _start_measurement(self):
        """ Start continuous measurement on mogwave server """
        self._dev.ask(b"start")

    def _stop_measurement(self):
        """ Stop continuous measurement on mogwave server """
        self._dev.ask(b"stop")

    def _get_wavelength(self):
        """ Get the current wavelength measurement, in vac nm"""
        temp = self._strip_response(self._dev.ask("wave,nm vac"))
        temp1 = temp.split(sep=' ')
        return float(temp1[1])

    def _strip_response(self, resp):
        """ Strip the "OK:" from the beginning of responses from server"""
        # the mogdevice class already checks for ERR: at the beginning of responses
        # so if we get this far we needn't check them. Instead, we can simply strip
        # the OK: from the front of each response.
        return resp[4:]
