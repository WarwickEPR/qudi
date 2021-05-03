# -*- coding: utf-8 -*-

""" Hardware module that controls the ANC350 via the PyANC350 module.
    Connects to the confocal scanner interface.
    All configuration is done in this file, until I work out how to do it in the config file."""

import time

from PyANC350.PyANC350v4 import Positioner
from core.module import Base
from core.configoption import ConfigOption
from interface.confocal_scanner_interface import ConfocalScannerInterface

# TODO: Should I import the confocal_scanner_spectrometer_interfuse?


class ConfocalScanner(Base, ConfocalScannerInterface):
    """
    """

    _modtype = 'AttocubeScanner'
    _modclass = 'hardware'

    pyanc = Positioner()

    # These variable should ideally be taken from the config file
    pos_range = [[0, 3e-3], [0, 3e-3], [0, 2e-3]]
    axis_name = ['x', 'y', 'z']
    attocube_axis = {'x': 0, 'y': 1, 'z': 2}
    tar_accuracy = 1e-6
    axis_pos = [0, 0, 0]

    def reset_hardware(self):
        """ Resets the hardware, so the connection is lost and other programs can access it.

        @return int: error code (0:OK, -1:error)
        """
        # AtNC350 doesn't really have a reset function. disconnect is the closest thing.
        self.pyanc.disconnect()

    def get_position_range(self):
        """ Returns the physical range of the scanner.

        @return float [N][2]: array of N ranges with an array containing lower and upper limit, preferably in SI unit.

        """
        return self.pos_range

    def set_position_range(self, myrange=None):
        """ Sets the physical range of the scanner.

        Deprecated : This range should not be accessible by logic. TODO: Discuss and remove from interface ?

        @param float [N][2] myrange: array of N ranges with an array containing lower and upper limit

        @return int: error code (0:OK, -1:error)
        """
        # Seems that this method is no deprecated, so can be ignored.
        pass

    def set_voltage_range(self, myrange=None):
        """ Sets the voltage range of the NI Card.

        Deprecated : This range should not be accessible by logic. TODO: Discuss and remove from interface ?

        @param float [2] myrange: array containing lower and upper limit

        @return int: error code (0:OK, -1:error)
        """
        # Same as above
        pass

    def get_scanner_axes(self):
        """ Find out how many axes the scanning device is using for confocal and their names.

        @return list(str): list of axis names

        Example:
          For 3D confocal microscopy in cartesian coordinates, ['x', 'y', 'z'] is a sensible value.
          For 2D, ['x', 'y'] would be typical.
          You could build a turntable microscope with ['r', 'phi', 'z'].
          Most callers of this function will only care about the number of axes, though.

          On error, return an empty list.
        """
        return self.axis_name

    # This method will likely have something to do with spectro. but for now is ignored
    def get_scanner_count_channels(self):
        """ Returns the list of channels that are recorded while scanning an image.

        @return list(str): channel names

        Most methods calling this might just care about the number of channels.
        """
        pass

    # Seems (from the TODOs) that this function can be ignored for now.
    # May be needed when integrating spectro. i.e. 1/frequency determines how long each exposure is
    def set_up_scanner_clock(self, clock_frequency=None, clock_channel=None):
        """ Configures the hardware clock of the hardware that controls the acquisition timing.

        @param float clock_frequency: if defined, this sets the frequency of the clock
        @param str clock_channel: if defined, this is the physical channel of the clock

        TODO: the clock_channel argument is unused and should not be known by the logic.
        TODO: Discuss and remove from interface ?

        @return int: error code (0:OK, -1:error)
        """
        pass

    # I think this one can be ignored for the time being
    def set_up_scanner(self, counter_channels=None, sources=None,
                       clock_channel=None, scanner_ao_channels=None):
        """ Configures the actual scanner with a given clock.

        @param str counter_channels: if defined, these are the physical conting devices
        @param str sources: if defined, these are the physical channels where
                                  the photons are to count from
        @param str clock_channel: if defined, this specifies the clock for the
                                  counter
        @param str scanner_ao_channels: if defined, this specifies the analoque
                                        output channels

        @return int: error code (0:OK, -1:error)

        TODO: Again, should the multiple clocks controlled by logic be in this interface ?
        """
        pass

    # TODO: What is the axis unit? Remember that
    # TODO: Fine tune final position using single steps, or replace autoMove with singleStep
    # In confocal_scanner_spectrometer_interfuse.py, this function is used to multiple times to complete
    # raster scan. Single step is much better for raster scan, but not ideal for moving back to start.
    def scanner_set_position(self, x=None, y=None, z=None, a=None):
        """ Move stage to x, y, z, a (where a is the fourth channel).

        @param float x: position in x-direction (in axis unit)
        @param float y: position in y-direction (in axis unit)
        @param float z: position in z-direction (in axis unit)
        @param float a: position in a-direction (in axis unit)

        @return int: error code (0:OK, -1:error)

        If a value is not set or set to None, the actual value is implied.
        """
        tar = [x, y, z, a]

        for axis in self.attocube_axis.values():
            self.pyanc.setAxisOutput(axis, 1, 1)
            self.pyanc.setTargetPosition(axis, tar[axis])
            self.pyanc.setTargetRange(axis, self.tar_accuracy)
            self.pyanc.setAxisOutput(axis, 1, 1)
            self.pyanc.startAutoMove(axis, 1, 0)

            # TODO: Remove print statements after confirming attocubes are moving as required
            time.sleep(0.5)
            t = 0
            while t == 0:
                c, e, m, t, eot_f, eot_b, error = self.pyanc.getAxisStatus(axis)
                if t == 0:
                    print('axis moving, currently at: ', self.pyanc.getPosition(axis))
                elif t == 1:
                    print('axis arrived at: ', self.pyanc.getPosition(axis))
                    self.pyanc.startAutoMove(axis, 0, 0)
                time.sleep(0.5)

    def get_scanner_position(self):
        """ Get the current position of the scanner hardware.

        @return tuple(float): current position as a tuple. Ex : (x, y, z, a).
        """
        for axis in self.attocube_axis.values():
            self.axis_pos[axis] = self.pyanc.getPosition(axis)

        pos = (self.axis_pos[0], self.axis_pos[1], self.axis_pos[2],)
        return pos

    # I think the confocal_scanner_spectrometer_interfuse handles the details of this function
    def scan_line(self, line_path=None, pixel_clock=False):
        """ Scans a line and returns the counts on that line.

        @param float[k][n] line_path: array k of n-part tuples defining the pixel positions
        @param bool pixel_clock: whether we need to output a pixel clock for this line

        TODO: Give a detail explanation of pixel_clock argument, how it is used in practice and why it is necessary.

        @return float[k][m]: the photon counts per second for k pixels with m channels
        """
        pass

    def close_scanner(self):
        """ Closes the scanner and cleans up afterwards.

        @return int: error code (0:OK, -1:error)

        TODO: Give a detail explanation how it is used in practice and why it is necessary.
        """

        for axis in self.attocube_axis.values():
            self.pyanc.setAxisOutput(axis, 0, 1)

        self.pyanc.disconnect()

    # This has no meaning in our setup, should be handled by confocal_scanner_spectrometer_interfuse
    def close_scanner_clock(self, power=0):
        """ Closes the clock and cleans up afterwards.

        @return int: error code (0:OK, -1:error)

        TODO: Give a detail explanation how it is used in practice and why it is necessary.
        """
        pass
