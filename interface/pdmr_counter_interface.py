# -*- coding: utf-8 -*-
from core.interface import abstract_interface_method
from core.meta import InterfaceMetaclass


class PDMRCounterInterface(metaclass=InterfaceMetaclass):
    """ This is the Interface class supplies the controls for a simple PDMR."""

    @abstract_interface_method
    def set_up_pdmr_clock(self, clock_frequency=None, clock_channel=None):
        """ Configures the hardware clock of the NiDAQ card to give the timing.

        @param float clock_frequency: if defined, this sets the frequency of the
                                      clock
        @param str clock_channel: if defined, this is the physical channel of
                                  the clock

        @return int: error code (0:OK, -1:error)
        """
        pass

    @abstract_interface_method
    def set_up_pdmr(self, counter_channel=None, photon_source=None,
                    clock_channel=None, pdmr_trigger_channel=None):
        """ Configures the actual counter with a given clock.

        @param str counter_channel: if defined, this is the physical channel of
                                    the counter
        @param str photon_source: if defined, this is the physical channel where
                                  the photons are to count from
        @param str clock_channel: if defined, this specifies the clock for the
                                  counter
        @param str pdmr_trigger_channel: if defined, this specifies the trigger
                                         output for the microwave

        @return int: error code (0:OK, -1:error)
        """
        pass

    @abstract_interface_method
    def set_pdmr_length(self, length=100):
        """Set up the trigger sequence for the PDMR and the triggered microwave.

        @param int length: length of microwave sweep in pixel

        @return int: error code (0:OK, -1:error)
        """
        pass

    @abstract_interface_method
    def count_pdmr(self, length = 100):
        """ Sweeps the microwave and returns the counts on that sweep.

        @param int length: length of microwave sweep in pixel

        @return (bool, float[]): tuple: was there an error, the current
        """
        pass

    @abstract_interface_method
    def close_pdmr(self):
        """ Close the pdmr and clean up afterwards.

        @return int: error code (0:OK, -1:error)
        """
        pass

    @abstract_interface_method
    def close_pdmr_clock(self):
        """ Close the pdmr and clean up afterwards.

        @return int: error code (0:OK, -1:error)
        """
        pass

    @abstract_interface_method
    def get_pdmr_channels(self):
        """ Return a list of channel names.

        @return list(str): channels recorded during PDMR measurement
        """
        pass

    @property
    @abstract_interface_method
    def oversampling(self):
        pass

    @oversampling.setter
    @abstract_interface_method
    def oversampling(self, val):
        pass

    @property
    @abstract_interface_method
    def lock_in_active(self):
        pass

    @lock_in_active.setter
    @abstract_interface_method
    def lock_in_active(self, val):
        pass
