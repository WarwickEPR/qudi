# -*- coding: utf-8 -*-
"""
This module controls LaserQuantum lasers.

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

from core.module import Base
from core.configoption import ConfigOption
from core.util.mutex import Mutex
from interface.simple_laser_interface import SimpleLaserInterface
from interface.simple_laser_interface import ControlMode
from interface.simple_laser_interface import ShutterState
from interface.simple_laser_interface import LaserState
from enum import Enum
import visa


class PSUTypes(Enum):
    """ LaserQuantum power supply types.
    """
    FPU = 0
    MPC6000 = 1
    MPC3000 = 2
    SMD12 = 3
    SMD6000 = 4


class LaserQuantumLaser(Base, SimpleLaserInterface):
    """ Qudi module to communicate with the Edwards turbopump and vacuum equipment.

    Example config for copy-paste:

    laserquantum_laser:
        module.Class: 'laser.laserquantum_laser.LaserQuantumLaser'
        interface: 'ASRL1::INSTR'
        maxpower: 0.250 # in Watt
        psu: 'SMD6000'

    """

    serial_interface = ConfigOption('interface', 'ASRL1::INSTR', missing='warn')
    maxpower = ConfigOption('maxpower', 0.250, missing='warn')
    psu_type = ConfigOption('psu', 'SMD6000', missing='warn')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.threadlock = Mutex()

    def on_activate(self):
        """ Activate module.
        """
        self.psu = PSUTypes[self.psu_type]
        self.connect_laser(self.serial_interface)

    def on_deactivate(self):
        """ Deactivate module.
        """
        self.disconnect_laser()

    def connect_laser(self, interface):
        """ Connect to Instrument.

            @param str interface: visa interface identifier

            @return bool: connection success
        """
        try:
            self.rm = visa.ResourceManager()
            rate = 9600 if self.psu in (PSUTypes.SMD6000, PSUTypes.SMD12) else 19200
            self.inst = self.rm.open_resource(
                interface,
                baud_rate=rate,
                write_termination='\r\n',
                read_termination='\r\n',
                send_end=True)
            # give laser 2 seconds maximum to reply
            self.inst.timeout = 2000
        except visa.VisaIOError:
            self.log.exception('Communication Failure:')
            return False
        else:
            return True

    def query(self, x):
        """Wrap VISA query to silence unhelpful errors from occasional failures to poll the GEM laser status"""
        attempts = 4
        exception = None
        for i in range(1, attempts):
            try:
                with self.threadlock:
                    return self.inst.query(x)
            except visa.VisaIOError as err:
                self.log.warn('LaserQuantum VISA query failed attempt {}'.format(i))
                exception = err
                # retry
                continue
        # tried but failed, re-raise latest of original exception
        raise visa.VisaIOError from exception

    def write(self, x):
        """Wrap VISA write to silence unhelpful errors from occasional failures to poll the GEM laser status"""
        attempts = 4
        exception = None
        for i in range(1, attempts):
            try:
                with self.threadlock:
                    return self.inst.write(x)
            except visa.VisaIOError as err:
                self.log.warn('LaserQuantum VISA write failed attempt {}'.format(i))
                exception = err
                # retry
                continue
        # tried but failed, re-raise latest of original exception
        raise visa.VisaIOError from exception


    def disconnect_laser(self):
        """ Close the connection to the instrument.
        """
        self.inst.close()
        self.rm.close()

    def allowed_control_modes(self):
        """ Control modes for this laser
        """
        if self.psu == PSUTypes.FPU:
            return [ControlMode.MIXED]
        elif self.psu in (PSUTypes.SMD6000, PSUTypes.SMD12):
            return [ControlMode.POWER]
        else:
            return [ControlMode.POWER, ControlMode.CURRENT]

    def get_control_mode(self):
        """ Get current laser control mode.

        @return ControlMode: current laser control mode
        """
        if self.psu == PSUTypes.FPU:
            return ControlMode.MIXED
        elif self.psu in (PSUTypes.SMD6000, PSUTypes.SMD12):
            return ControlMode.POWER
        else:
            return ControlMode[self.query('CONTROL?')]

    def set_control_mode(self, mode):
        """ Set laser control mode.

        @param ControlMode mode: desired control mode
        @return ControlMode: actual control mode
        """
        if self.psu == PSUTypes.FPU:
            return ControlMode.MIXED
        elif self.psu in (PSUTypes.SMD6000, PSUTypes.SMD12):
            return ControlMode.POWER
        else:
            if mode == ControlMode.POWER:
                reply1 = self.query('PFB=OFF')
                reply2 = self.query('CONTROL=POWER')
                self.log.debug("Set POWER control mode {0}, {1}.".format(reply1, reply2))
            else:
                reply1 = self.query('PFB=ON')
                reply2 = self.query('CONTROL=CURRENT')
                self.log.debug("Set CURRENT control mode {0}, {1}.".format(reply1, reply2))
        return self.get_control_mode()

    def get_power(self):
        """ Get laser power.

            @return float: laser power in watts
        """
        attempts = 3
        exception = None
        answer = ''
        for i in range(1, attempts):
            try:
                answer = self.query('POWER?')
                if "mW" in answer:
                    return float(answer.split('mW')[0]) / 1000
                elif 'W' in answer:
                    return float(answer.split('W')[0])
                else:
                    return float(answer)
            except ValueError as err:
                self.log.exception("Laser 'POWER?' unexpected response {0}.".format(answer))
                exception = err
                # retry
                continue

        # tried but failed, re-raise latest of original exception
        raise exception

    def get_power_setpoint(self):
        """ Get the laser power setpoint.

        @return float: laser power setpoint in watts
        """
        if self.psu == PSUTypes.FPU:
            answer = self.query('SETPOWER?')
            try:
                if "mW" in answer:
                    return float(answer.split('mW')[0]) / 1000
                elif 'W' in answer:
                    return float(answer.split('W')[0])
                else:
                    return float(answer)
            except ValueError:
                self.log.exception("Answer was {0}.".format(answer))
                return -1
        else:
            return self.get_power()

    def get_power_range(self):
        """ Get laser power range.

        @return tuple(float, float): laser power range
        """
        return 0, self.maxpower

    def set_power(self, power):
        """ Set laser power

        @param float power: desired laser power in watts
        """
        if self.psu == PSUTypes.FPU:
            self.query('POWER={0:f}'.format(power))
        else:
            self.query('POWER={0:f}'.format(power*1000))

    def get_current_unit(self):
        """ Get unit for laser current.

            @return str: unit for laser current
        """
        return '%'

    def get_current_range(self):
        """ Get range for laser current.

            @return tuple(flaot, float): range for laser current
        """
        return 0, 100

    def get_current(self):
        """ Get current laser current

        @return float: current laser current
        """

        attempts = 3
        exception = None
        answer = ''
        for i in range(1, attempts):
            try:
                if self.psu == PSUTypes.MPC3000 or self.psu == PSUTypes.MPC6000:
                    answer = self.query('SETCURRENT1?')
                    return float(answer.split('%')[0])
                else:
                    answer = self.query('CURRENT?')
                    return float(answer.split('%')[0])
            except ValueError as err:
                self.log.exception("Laser 'CURRENT?/SETCURRENT?' unexpected response {0}.".format(answer))
                exception = err
                # retry
                continue

        # tried but failed, re-raise latest of original exception
        raise exception

    def get_set_current(self):
        """ Get current current laser current setpoint

        @return float: laser current setpoint
        """

        attempts = 3
        exception = None
        answer = ''
        for i in range(1, attempts):
            try:
                if self.psu in (PSUTypes.MPC3000, PSUTypes.MPC6000):
                    answer = self.query('SETCURRENT1?')
                elif self.psu in (PSUTypes.SMD6000, PSUTypes.SMD12):
                    answer = self.query('CURRENT?')
                else:
                    answer = self.query('SETCURRENT?')
                return float(answer.split('%')[0])
            except ValueError as err:
                self.log.exception("Laser 'SETCURRENT?/CURRENT?' unexpected response {0}.".format(answer))
                exception = err
                # retry
                continue

        # tried but failed, re-raise latest of original exception
        raise exception


    def get_current_setpoint(self):
        """ Current laser current setpoint.

        @return float: laser current setpoint
        """

    def set_current(self, current_percent):
        """ Set laser current setpoint.

        @param float current_percent: laser current setpoint
        """
        self.query('CURRENT={0}'.format(current_percent))
        return self.get_current()

    def get_shutter_state(self):
        """ Get laser shutter state.

        @return ShutterState: laser shutter state
        """
        if self.psu == PSUTypes.FPU:
            state = self.query('SHUTTER?')
            if 'OPEN' in state:
                return ShutterState.OPEN
            elif 'CLOSED' in state:
                return ShutterState.CLOSED
            else:
                return ShutterState.UNKNOWN
        else:
            return ShutterState.NOSHUTTER

    def set_shutter_state(self, state):
        """ Set the desired laser shutter state.

        @param ShutterState state: desired laser shutter state
        @return ShutterState: actual laser shutter state
        """
        if self.psu == PSUTypes.FPU:
            actstate = self.get_shutter_state()
            if state != actstate:
                if state == ShutterState.OPEN:
                    self.query('SHUTTER OPEN')
                elif state == ShutterState.CLOSED:
                    self.query('SHUTTER CLOSE')
        return self.get_shutter_state()

    def get_psu_temperature(self):
        """ Get power supply temperature

        @return float: power supply temperature
        """
        attempts = 3
        exception = None
        answer = ''
        for i in range(1, attempts):
            try:
                answer = self.query('PSUTEMP?')
                return float(answer.split('C')[0])
            except ValueError as err:
                self.log.exception("Laser 'PSUTEMP?' unexpected response {0}.".format(answer))
                exception = err
                # retry
                continue

        # tried but failed, re-raise latest of original exception
        raise exception

    def get_laser_temperature(self):
        """ Get power supply temperature

        @return float: power supply temperature
        """
        attempts = 3
        exception = None
        answer = ''
        for i in range(1, attempts):
            try:
                answer = self.query('LASTEMP?')
                return float(answer.split('C')[0])
            except ValueError as err:
                self.log.exception("Laser 'LASTEMP?' unexpected response {0}.".format(answer))
                exception = err
                # retry
                continue

        # tried but failed, re-raise latest of original exception
        raise exception

    def get_temperatures(self):
        """ Get all available temperatures.

            @return dict: dict of temperature names and value
        """
        return {
            'psu': self.get_psu_temperature(),
            'laser': self.get_laser_temperature()
            }

    def set_temperatures(self, temps):
        """ Set temperature for lasers with adjustable temperature for tuning

            @return dict: dict with new temperature setpoints
        """
        return {}

    def get_temperature_setpoints(self):
        """ Get temperature setpints.

            @return dict: dict of temperature name and setpoint value
        """
        return {}

    def get_lcd(self):
        """ Get the text displayed on the PSU display.

            @return str: text on power supply display
        """
        if self.psu in(PSUTypes.SMD12, PSUTypes.SMD600):
            return ''
        else:
            return self.query('STATUSLCD?')

    def get_laser_state(self):
        """ Get laser operation state

        @return LaserState: laser state
        """
        if self.psu == PSUTypes.SMD6000:
            state = self.query('STAT?')
        else:
            state = self.query('STATUS?')
        if 'ENABLED' in state:
            return LaserState.ON
        elif 'DISABLED' in state:
            return LaserState.OFF
        else:
            return LaserState.UNKNOWN

    def set_laser_state(self, status):
        """ Set desited laser state.

        @param LaserState status: desired laser state
        @return LaserState: actual laser state
        """
        actstat = self.get_laser_state()
        if actstat != status:
            if status == LaserState.ON:
                self.query('ON')
            elif status == LaserState.OFF:
                self.query('OFF')
        return self.get_laser_state()

    def on(self):
        """ Turn laser on.

            @return LaserState: actual laser state
        """
        return self.set_laser_state(LaserState.ON)

    def off(self):
        """ Turn laser off.

            @return LaserState: actual laser state
        """
        return self.set_laser_state(LaserState.OFF)

    def get_firmware_version(self):
        """ Ask the laser for ID.

        @return str: what the laser tells you about itself
        """
        if self.psu == PSUTypes.SMD6000:
            self.write('VERSION')
        else:
            self.write('SOFTVER?')
        lines = []
        try:
            while True:
                lines.append(self.inst.read())
        except:
            pass
        return lines

    def dump(self):
        """ Return LaserQuantum information dump

        @return str: diagnostic information dump from laser
        """
        self.write('DUMP ')
        lines = []
        try:
            while True:
                lines.append(self.inst.read())
        except:
            pass
        return lines

    def timers(self):
        """ Return information about component runtimes.

            @return str: runtimes of components
        """
        self.write('TIMERS')
        lines = []
        try:
            while True:
                lines.append(self.inst.read())
        except:
            pass
        return lines

    def get_extra_info(self):
        """ Extra information from laser.

            @return str: multiple lines of text with information about laser

            For LaserQuantum devices, this is the firmware version, dump and timers information
        """
        extra = ''
        extra += '\n'.join(self.get_firmware_version())
        extra += '\n'
        if self.psu == PSUTypes.FPU:
            extra += '\n'.join(self.dump())
            extra += '\n'
        extra += '\n'.join(self.timers())
        extra += '\n'
        return extra

