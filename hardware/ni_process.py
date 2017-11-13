# -*- coding: utf-8 -*-
"""
Process control with an NI input and output, software polling OnDemand

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

from interface.process_interface import ProcessInterface
from interface.process_control_interface import ProcessControlInterface
from core.module import Base, ConfigOption
import PyDAQmx as daq


class NIProcess(Base, ProcessInterface, ProcessControlInterface):
    """ Methods to control a system using NI AI and AO
    """
    _modclass = 'NIProcess'
    _modtype = 'hardware'

    _input_channel = ConfigOption('inputChannel', missing='error')
    _output_channel = ConfigOption('outputChannel', missing='error')
    _input_minimum = ConfigOption('outputMinimum', 0.0, missing='warning')
    _input_maximum = ConfigOption('outputMaximum', 10.0, missing='warning')
    _name = ConfigOption('name', missing='error')

    def on_activate(self):
        """ Activate module.
        """

        config = self.getConfiguration()

        # configure analog out
        self.inputChannel = config['inputChannel']
        self.outputChannel = config['outputChannel']
        self.minV = config['outputMinimum']
        self.minV = config['outputMaximum']
        self.outputName = config['name'] + 'Out'
        self.inputName = config['name'] + 'In'
        timeout = 10

        # create input task
        self.inputTask = daq.TaskHandle()
        daq.DAQmxCreateTask(self.inputName + 'Task', daq.byref(self.inputTask))

        # create output task
        self.outputTask = daq.TaskHandle()
        daq.DAQmxCreateTask(self.outputName + 'Task', daq.byref(self.outputTask))

        # create output channel and write voltage
        daq.DAQmxCreateAOVoltageChan(self.outputTask, self.outputChannel, self.outputTaskName + 'Channel',
                                     self.minV, self.maxV, daq.DAQmx_Val_Volts, None)

        # create input channel and write voltage
        daq.DAQmxCreateAIVoltageChan(self.inputTask, self.inputChannel, self.inputTaskName + 'Channel',
                                     daq.DAQmx_Val_RSE, self.minV, self.maxV, daq.DAQmx_Val_Volts, None)


    def on_deactivate(self):
        """ Deactivate module.
        """
        daq.DAQmxStopTask(self.inputTask)
        daq.DAQmxClearTask(self.inputTask)
        daq.DAQmxStopTask(self.outputTask)
        daq.DAQmxClearTask(self.outputTask)

    # Convert to mW for a laser controller
    def getProcessValue(self):
        """ Process value

            @return float: process value
        """
        return daq.DAQmxReadAnalogScalarF64(self.inputTask, 0.1)

    def getProcessUnit(self):
        """ Process unit, here kelvin.

            @return float: process unit
        """
        return ('V', 'volts')

    def setControlValue(self, value):
        """ Set control value, here heating power.

            @param float value: control value
        """
        self.controlValue = value
        daq.DAQmxWriteAnalogScalarF64(self.outputTask, True, 0.1, value, None)

    def getControlValue(self):
        """ Get current control value, here heating power

            @return float: current control value
        """
        return self.controValue

    def getControlUnit(self):
        """ Get unit of control value.

            @return tuple(str): short and text unit of control value
        """
        return ('V', 'voltage')

    def getControlLimits(self):
        """ Get minimum and maximum of control value.

            @return tuple(float, float): minimum and maximum of control value
        """
        return (self.minV, self.maxV)
