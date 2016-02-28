# -*- coding: utf-8 -*-
"""
This file contains the QuDi gated counter logic class.

QuDi is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

QuDi is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with QuDi. If not, see <http://www.gnu.org/licenses/>.

Copyright (C) 2016 Alexander Stark alexander.stark@uni-ulm.de
"""

from logic.generic_logic import GenericLogic
from PyQt4 import QtGui, QtCore
import numpy as np
import time


class TraceAnalysisLogic(GenericLogic):
    """ Perform a gated counting measurement with the hardware.  """

    _modclass = 'traceanalysislogic'
    _modtype = 'logic'

    ## declare connectors
    _in = { 'counterlogic1': 'CounterLogic',
            'savelogic': 'SaveLogic'
            }
    _out = {'traceanalysislogic1': 'TraceAnalysisLogic'}

    sigHistogramUpdated = QtCore.Signal()


    def __init__(self, manager, name, config, **kwargs):
        """ Create CounterLogic object with connectors.

          @param object manager: Manager object thath loaded this module
          @param str name: unique module name
          @param dict config: module configuration
          @param dict kwargs: optional parameters
        """
        ## declare actions for state transitions
        state_actions = {'onactivate': self.activation,
                         'ondeactivate': self.deactivation}
        super().__init__(manager, name, config, state_actions, **kwargs)

        self.logMsg('The following configuration was found.', msgType='status')

        # checking for the right configuration
        for key in config.keys():
            self.logMsg('{}: {}'.format(key,config[key]),
                        msgType='status')

        # empty_trace = np.zeros((100,))
        # empty_trace = np.random.randint(1000, size=100)
        # self.trace_obj = None   # the new trace object will be saved here
        # self.histogram = np.zeros((2,100))
        # self.create_new_trace(empty_trace)
        #
        # self._trace

        self.hist_data = None
        self._hist_num_bins = None

    def activation(self, e):
        """ Initialisation performed during activation of the module.

        @param object e: Event class object from Fysom.
                         An object created by the state machine module Fysom,
                         which is connected to a specific event (have a look in
                         the Base Class). This object contains the passed event
                         the state before the event happens and the destination
                         of the state which should be reached after the event
                         has happen.
        """

        self._counter_logic = self.connector['in']['counterlogic1']['object']
        self._save_logic = self.connector['in']['savelogic']['object']

        self._counter_logic.sigGatedCounterFinished.connect(self.do_calculate_histogram)

    def deactivation(self, e):
        """ Deinitialisation performed during deactivation of the module.

        @param object e: Event class object from Fysom. A more detailed
                         explanation can be found in method activation.
        """
        return




    def set_num_bins_histogram(self, num_bins, update=True):
        """ Set the number of bins

        @param int num_bins: number of bins for the histogram
        @param bool update: if the change of bins should evoke a recalculation
                            of the histogram.
        """
        self._hist_num_bins = num_bins

        if update:
            self.do_calculate_histogram()

    def do_calculate_histogram(self):
        """ Passes all the needed parameters to the appropriated methods.

        @return:
        """

        self.hist_data = self.calculate_histogram(self._counter_logic.countdata,
                                                  self._hist_num_bins)


        self.sigHistogramUpdated.emit()



    def calculate_histogram(self, trace, num_bins=None, custom_bin_arr=None):
        """ Calculate the histogram of a given trace.

        @param np.array trace: a 1D trace
        @param int num_bins: number of bins between the minimal and maximal
                             value of the trace. That must be an integer greater
                             than or equal to 1.
        @param np.array custom_bin_arr: optional, 1D array. If a specific,
                                        non-uniform binning array is desired
                                        then it can be passed to the numpy
                                        routine. Then the parameter num_bins is
                                        ignored. Otherwise a uniform binning is
                                        applied by default.
        @return: np.array: a 2D array, where first entry are the x_values and
                           second entry are the count values. The length of the
                           array is normally determined by the num_bins
                           parameter.

        Usually the bins for the histogram are taken to be equally spaced,
        ranging from the minimal to the maximal value of the input trace array.
        """

        if custom_bin_arr is not None:
            hist_y_val, hist_x_val = np.histogram(trace, custom_bin_arr,
                                                  density=False)
        else:

            # analyze the trace,
            difference = trace.max() - trace.min()

            if np.isclose(0, difference) or num_bins is None:
                # numpy can handle an array of zeros
                hist_y_val, hist_x_val = np.histogram(trace)
            else:
                # a histogram with self defined number of bins
                hist_y_val, hist_x_val = np.histogram(trace, num_bins)


        return hist_x_val, hist_y_val







    #
    # def set_binning(self, binning, update=True):
    #     """ Change the binning of the histogram and redo the histogram
    #
    #     @param int binning: number of bins in the trace.
    #     @param bool update: optional, set whether the histogram should be
    #                         updated
    #     @return:
    #     """
    #     self.trace_obj.change_binning(binning)
    #
    #     if update:
    #         self.create_histogram()
    #
    # def create_histogram(self):
    #     """ Creates the histogram
    #
    #     @return:
    #     """
    #
    #     self.trace_obj.create_hist()
    #
    #
    #     self.histogram = np.array((self.trace_obj.bins, self.trace_obj.hist))
    #
    #     self.sigHistogramUpdated.emit()
    #
    #
    # """
    # - Methods for histogram
    #
    # """

    # def create_new_trace(self, trace=None):
    #     """ Create a new Trace Analysis object, which can be analyzed.
    #
    #     @param np.array trace: a 1D trace
    #
    #     Overwrites the trace object saved in this class.
    #     """
    #
    #     if trace is None:
    #         self.trace_obj = Trace(self._counter_logic.countdata)
    #     else:
    #         self.trace_obj = Trace(trace)
    #
    #     self.create_histogram()