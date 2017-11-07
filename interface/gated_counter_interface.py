# -*- coding: utf-8 -*-
"""
This file contains the Qudi Interface file for counters gated by a trigger channel

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

import abc
from core.util.interfaces import InterfaceMetaclass

class GatedCounterInterface(metaclass=InterfaceMetaclass):
    """ Interface to a counter returning a finite number of counts gated by some signal."""

    _modtype = 'GatedCounterInterface'
    _modclass = 'interface'

    @abc.abstractmethod
    def configure_gated_counter(self, name, n, click_channel, start_channel, stop_channel=None):
        """ Configure a new gated counter

        @param str name : name for this gated counter (can be added runtime with different parameters & triggers)
        @param int n    : number of points to collect (expect n+1 triggers)
        @param str click_channel : channel for photon counts
        @param str start_channel : channel to trigger start of each bin
        @param str end_channel   : if supplied, end counting each bin. By default, uses the start_channel

        (Implicitly may start counting, but doesn't lock the instrument)
        """
        pass

    @abc.abstractmethod
    def start_gated_counter(self, name):
        """ Start the gated counter. (and locks)
        @param str name : name of configured gated counter
        Resets and starts counting"""
        pass

    @abc.abstractmethod
    def stop_gated_counter(self, name):
        """ Stop the gated counter. (and unlocks)
        @param str name : name of configured gated counter """
        pass

    @abc.abstractmethod
    def pause_gated_counter(self, name):
        """ Pauses the current gated_counter measurement, if allowed.
        @param str name : name of configured gated counter """
        pass

    @abc.abstractmethod
    def continue_gated_counter(self, name):
        """ Continues the current measurement.
        @param str name : name of configured gated counter

        If in pause state, then gated counter will be continued.
        """
        pass

    @abc.abstractmethod
    def get_rates_gated_counter(self, name):
        """ Get completed rates for current measurement
        @param str name : name of configured gated counter

        @return numpy int64 array : array of up to n rates gathered so far in counts/s (count/bin length)
        """
        pass

    @abc.abstractmethod
    def reset_gated_counter(self, name):
        """ Reset this counter. Immediately starts collecting
        @param str name : name of configured gated counter"""
        pass

    @abc.abstractmethod
    def setup_gated_counter(self, start_channel, stop_channel=None, n=1):
        """ Sets up a counter to find the count rate between markers for a finite number of points

        @param str start_channel: channel giving markers between bins
        @param str stop_channel: channel giving marker to stop counting each bin
        @param int n: number of samples which are expected

        @return int: error code (0:OK, -1:error)
        """
        pass