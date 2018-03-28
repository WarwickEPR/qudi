"""
This module manages the stages attached to the Agilis Controller

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

import time
# import numpy as np

from qtpy import QtCore
from core.module import Connector, ConfigOption, StatusVar
from logic.generic_logic import GenericLogic
# from collections import OrderedDict






class AgilisLogic(GenericLogic):
    """
    This is the logic for utilising Agilis stages and recording the data
    """

    _modclass = 'agilis'
    _modtype = 'logic'

    motorstage = Connector(interface='MotorInterface')

    # Keep track of motor motion
    sigUpdate = QtCore.Signal()

    def on_activate(self):
        """ Connect to the controller """
        self._motor_stage = self.get_connector('motor')
        self.stopRequest = False
        self.bufferLength = 100
        self.data = {}
        # waiting time between queries im milliseconds
        self.queryInterval = 100

        # delay timer for querying motor
        self.queryTimer = QtCore.QTimer()
        self.queryTimer.setInterval(self.queryInterval)
        self.queryTimer.setSingleShot(True)
        self.queryTimer.timeout.connect(self.check_motor_loop(), QtCore.Qt.QueuedConnection)

        # get motor capabilities
        # Get current position
        self.motor_position = self._motor_stage.get_pos()
        # Find out if the motor is moving or not
        self.motor_moving = self._motor_stage.get_status()
        # Found out the step amplitude / Velocity
        self.motor_velocity = self._motor_stage.get_velocity()
        # Return the motor constraints
        self.motor_constraints = self._motor_stage.get_constraints()

        self.init_data_logging()
        self.start_query_loop()

    def on_deactivate(self):
        """ Deactivate module.
        """
        self.stop_query_loop()
        for i in range(5):
            time.sleep(self.queryInterval / 1000)
            QtCore.QCoreApplication.processEvents()

    @QtCore.Slot()
    def check_motor_loop(self):
        """ Gets the motor status from the controller """
        qi = self.queryInterval

        # get stuff?
        try:
            # Find the physical position
            self.motor_position = self._motor_stage.get_pos()
            # Find out if the motor is moving or not
            self.motor_moving = self._motor_stage.get_status()
            # Found out the step amplitude / Velocity
            self.motor_velocity = self._motor_stage.get_velocity()

        except:
            qi = 3000
            self.log.exception("Something went wrong with the check_motor_loop")

        self.queryTimer.start(qi)
        self.sigUpdate.emit()


# -*- coding: utf-8 -*-

"""
This file contains the general logic for magnet control.

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


class MagnetLogic(GenericLogic):
    """ A general magnet logic to control an magnetic stage with an arbitrary
        set of axis.

    DISCLAIMER:
    ===========

    The current status of the magnet logic is highly experimental and not well
    tested. The implementation has some considerable imperfections. The state of
    this module is considered to be UNSTABLE.

    This module has two major issues:
        - a lack of proper documentation of all the methods
        - usage of tasks is not implemented and therefore direct connection to
          all the modules is used (I tried to compress as good as possible all
          the part, where access to other modules occurs so that a later
          replacement would be easier and one does not have to search throughout
          the whole file.)

    However, the 'high-level state maschine' for the alignment should be rather
    general and very powerful to use. The different state were divided in
    several consecutive methods, where each method can be implemented
    separately and can be extended for custom needs. (I have drawn a diagram,
    which is much more telling then the documentation I can write down here.)

    I am currently working on that and will from time to time improve the status
    of this module. So if you want to use it, be aware that there might appear
    drastic changes.

    ---
    Alexander Stark
    """

    _modclass = 'MagnetLogic'
    _modtype = 'logic'

    ## declare connectors
    magnetstage = Connector(interface='MagnetInterface')
    optimizerlogic = Connector(interface='OptimizerLogic')
    counterlogic = Connector(interface='CounterLogic')
    odmrlogic = Connector(interface='ODMRLogic')
    savelogic = Connector(interface='SaveLogic')
    scannerlogic = Connector(interface='ScannerLogic')
    traceanalysis = Connector(interface='TraceAnalysisLogic')
    gatedcounterlogic = Connector(interface='GatedCounterLogic')
    sequencegeneratorlogic = Connector(interface='SequenceGeneratorLogic')

    align_2d_axis0_range = StatusVar('align_2d_axis0_range', 10e-3)
    align_2d_axis0_step = StatusVar('align_2d_axis0_step', 1e-3)
    align_2d_axis0_vel = StatusVar('align_2d_axis0_vel', 10e-6)
    align_2d_axis1_range = StatusVar('align_2d_axis1_range', 10e-3)
    align_2d_axis1_step = StatusVar('align_2d_axis1_step', 1e-3)
    align_2d_axis1_vel = StatusVar('align_2d_axis1_vel', 10e-6)
    curr_2d_pathway_mode = StatusVar('curr_2d_pathway_mode', 'snake-wise')

    _checktime = StatusVar('_checktime', 2.5)
    _1D_axis0_data = StatusVar('_1D_axis0_data', np.zeros(2))
    _2D_axis0_data = StatusVar('_2D_axis0_data', np.zeros(2))
    _2D_axis1_data = StatusVar('_2D_axis1_data', np.zeros(2))
    _3D_axis0_data = StatusVar('_3D_axis0_data', np.zeros(2))
    _3D_axis1_data = StatusVar('_3D_axis1_data', np.zeros(2))
    _3D_axis2_data = StatusVar('_3D_axis2_data', np.zeros(2))

    _2D_data_matrix = StatusVar('_2D_data_matrix', np.zeros((2, 2)))
    _3D_data_matrix = StatusVar('_3D_data_matrix', np.zeros((2, 2, 2)))

    curr_alignment_method = StatusVar('curr_alignment_method', '2d_fluorescence')
    _optimize_pos_freq = StatusVar('_optimize_pos_freq', 1)

    _fluorescence_integration_time = StatusVar('_fluorescence_integration_time', 5)
    odmr_2d_low_center_freq = StatusVar('odmr_2d_low_center_freq', 11028e6)
    odmr_2d_low_step_freq = StatusVar('odmr_2d_low_step_freq', 0.15e6)
    odmr_2d_low_range_freq = StatusVar('odmr_2d_low_range_freq', 25e6)
    odmr_2d_low_power = StatusVar('odmr_2d_low_power', 4)
    odmr_2d_low_runtime = StatusVar('odmr_2d_low_runtime', 40)

    odmr_2d_high_center_freq = StatusVar('odmr_2d_high_center_freq', 16768e6)
    odmr_2d_high_step_freq = StatusVar('odmr_2d_high_step_freq', 0.15e6)
    odmr_2d_high_range_freq = StatusVar('odmr_2d_high_range_freq', 25e6)
    odmr_2d_high_power = StatusVar('odmr_2d_high_power', 2)
    odmr_2d_high_runtime = StatusVar('odmr_2d_high_runtime', 40)
    odmr_2d_save_after_measure = StatusVar('odmr_2d_save_after_measure', True)
    odmr_2d_peak_axis0_move_ratio = StatusVar('odmr_2d_peak_axis0_move_ratio', 0)
    odmr_2d_peak_axis1_move_ratio = StatusVar('odmr_2d_peak_axis1_move_ratio', 0)

    nuclear_2d_rabi_periode = StatusVar('nuclear_2d_rabi_periode', 1000e-9)
    nuclear_2d_mw_freq = StatusVar('nuclear_2d_mw_freq', 100e6)
    nuclear_2d_mw_channel = StatusVar('nuclear_2d_mw_channel', -1)
    nuclear_2d_mw_power = StatusVar('nuclear_2d_mw_power', -30)
    nuclear_2d_laser_time = StatusVar('nuclear_2d_laser_time', 900e-9)
    nuclear_2d_laser_channel = StatusVar('nuclear_2d_laser_channel', 2)
    nuclear_2d_detect_channel = StatusVar('nuclear_2d_detect_channel', 1)
    nuclear_2d_idle_time = StatusVar('nuclear_2d_idle_time', 1500e-9)
    nuclear_2d_reps_within_ssr = StatusVar('nuclear_2d_reps_within_ssr', 1000)
    nuclear_2d_num_ssr = StatusVar('nuclear_2d_num_ssr', 3000)

    # General Signals, used everywhere:
    sigIdleStateChanged = QtCore.Signal(bool)
    sigPosChanged = QtCore.Signal(dict)

    sigMeasurementStarted = QtCore.Signal()
    sigMeasurementContinued = QtCore.Signal()
    sigMeasurementStopped = QtCore.Signal()
    sigMeasurementFinished = QtCore.Signal()

    # Signals for making the move_abs, move_rel and abort independent:
    sigMoveAbs = QtCore.Signal(dict)
    sigMoveRel = QtCore.Signal(dict)
    sigAbort = QtCore.Signal()
    sigVelChanged = QtCore.Signal(dict)

    # Alignment Signals, remember do not touch or connect from outer logic or
    # GUI to the leading underscore signals!
    _sigStepwiseAlignmentNext = QtCore.Signal()
    _sigContinuousAlignmentNext = QtCore.Signal()
    _sigInitializeMeasPos = QtCore.Signal(bool)  # signal to go to the initial measurement position
    sigPosReached = QtCore.Signal()

    # signals if new data are writen to the data arrays (during measurement):
    sig1DMatrixChanged = QtCore.Signal()
    sig2DMatrixChanged = QtCore.Signal()
    sig3DMatrixChanged = QtCore.Signal()

    # signals if the axis for the alignment are changed/renewed (before a measurement):
    sig1DAxisChanged = QtCore.Signal()
    sig2DAxisChanged = QtCore.Signal()
    sig3DAxisChanged = QtCore.Signal()

    # signals for 2d alignemnt general
    sig2DAxis0NameChanged = QtCore.Signal(str)
    sig2DAxis0RangeChanged = QtCore.Signal(float)
    sig2DAxis0StepChanged = QtCore.Signal(float)
    sig2DAxis0VelChanged = QtCore.Signal(float)

    sig2DAxis1NameChanged = QtCore.Signal(str)
    sig2DAxis1RangeChanged = QtCore.Signal(float)
    sig2DAxis1StepChanged = QtCore.Signal(float)
    sig2DAxis1VelChanged = QtCore.Signal(float)

    sigMoveRelChanged = QtCore.Signal(dict)

    # signals for fluorescence alignment
    sigFluoIntTimeChanged = QtCore.Signal(float)
    sigOptPosFreqChanged = QtCore.Signal(float)

    # signal for ODMR alignment
    sigODMRLowFreqChanged = QtCore.Signal()
    sigODMRHighFreqChanged = QtCore.Signal()

    sigTest = QtCore.Signal()

    def __init__(self, config, **kwargs):
        super().__init__(config=config, **kwargs)

        self._stop_measure = False

    def on_activate(self):
        """ Definition and initialisation of the GUI.
        """
        self._magnet_device = self.get_connector('magnetstage')
        self._save_logic = self.get_connector('savelogic')

        # FIXME: THAT IS JUST A TEMPORARY SOLUTION! Implement the access on the
        #       needed methods via the TaskRunner!
        self._optimizer_logic = self.get_connector('optimizerlogic')
        self._confocal_logic = self.get_connector('scannerlogic')
        self._counter_logic = self.get_connector('counterlogic')
        self._odmr_logic = self.get_connector('odmrlogic')

        self._gc_logic = self.get_connector('gatedcounterlogic')
        self._ta_logic = self.get_connector('traceanalysis')
        # self._odmr_logic = self.get_connector('odmrlogic')

        self._seq_gen_logic = self.get_connector('sequencegeneratorlogic')

        # EXPERIMENTAL:
        # connect now directly signals to the interface methods, so that
        # the logic object will be not blocks and can react on changes or abort
        self.sigMoveAbs.connect(self._magnet_device.move_abs)
        self.sigMoveRel.connect(self._magnet_device.move_rel)
        self.sigAbort.connect(self._magnet_device.abort)
        self.sigVelChanged.connect(self._magnet_device.set_velocity)

        # signal connect for alignment:

        self._sigInitializeMeasPos.connect(self._move_to_curr_pathway_index)
        self._sigStepwiseAlignmentNext.connect(self._stepwise_loop_body,
                                               QtCore.Qt.QueuedConnection)

        self.pathway_modes = ['spiral-in', 'spiral-out', 'snake-wise', 'diagonal-snake-wise']

        # relative movement settings

        constraints = self._magnet_device.get_constraints()
        self.move_rel_dict = {}

        for axis_label in constraints:
            if ('move_rel_' + axis_label) in self._statusVariables:
                self.move_rel_dict[axis_label] = self._statusVariables[('move_rel_' + axis_label)]
            else:
                self.move_rel_dict[axis_label] = 1e-3

        # 2D alignment settings

        if 'align_2d_axis0_name' in self._statusVariables:
            self.align_2d_axis0_name = self._statusVariables['align_2d_axis0_name']
        else:
            axes = list(self._magnet_device.get_constraints())
            self.align_2d_axis0_name = axes[0]
        if 'align_2d_axis1_name' in self._statusVariables:
            self.align_2d_axis1_name = self._statusVariables['align_2d_axis1_name']
        else:
            axes = list(self._magnet_device.get_constraints())
            self.align_2d_axis1_name = axes[1]

        self.sigTest.connect(self._do_premeasurement_proc)

        if '_1D_add_data_matrix' in self._statusVariables:
            self._1D_add_data_matrix = self._statusVariables['_1D_add_data_matrix']
        else:
            self._1D_add_data_matrix = np.zeros(shape=np.shape(self._1D_axis0_data), dtype=object)

        if '_2D_add_data_matrix' in self._statusVariables:
            self._2D_add_data_matrix = self._statusVariables['_2D_add_data_matrix']
        else:
            self._2D_add_data_matrix = np.zeros(shape=np.shape(self._2D_data_matrix), dtype=object)

        if '_3D_add_data_matrix' in self._statusVariables:
            self._3D_add_data_matrix = self._statusVariables['_3D_add_data_matrix']
        else:
            self._3D_add_data_matrix = np.zeros(shape=np.shape(self._3D_data_matrix), dtype=object)

        self.alignment_methods = ['2d_fluorescence', '2d_odmr', '2d_nuclear']

        self.odmr_2d_low_fitfunction_list = self._odmr_logic.get_fit_functions()

        if 'odmr_2d_low_fitfunction' in self._statusVariables:
            self.odmr_2d_low_fitfunction = self._statusVariables['odmr_2d_low_fitfunction']
        else:
            self.odmr_2d_low_fitfunction = list(self.odmr_2d_low_fitfunction_list)[1]

        self.odmr_2d_high_fitfunction_list = self._odmr_logic.get_fit_functions()

        if 'odmr_2d_high_fitfunction' in self._statusVariables:
            self.odmr_2d_high_fitfunction = self._statusVariables['odmr_2d_high_fitfunction']
        else:
            self.odmr_2d_high_fitfunction = list(self.odmr_2d_high_fitfunction_list)[1]

        # that is just a normalization value, which is needed for the ODMR
        # alignment, since the colorbar cannot display values greater (2**32)/2.
        # A solution has to found for that!
        self.norm = 1000

        # use that if only one ODMR transition is available.
        self.odmr_2d_single_trans = False

    def on_deactivate(self):
        """ Deactivate the module properly.
        """
        constraints = self.get_hardware_constraints()
        for axis_label in constraints:
            self._statusVariables[('move_rel_' + axis_label)] = self.move_rel_dict[axis_label]

        self._statusVariables['align_2d_axis0_name'] = self.align_2d_axis0_name
        self._statusVariables['align_2d_axis1_name'] = self.align_2d_axis1_name

        self._statusVariables['odmr_2d_low_fitfunction'] = self.odmr_2d_low_fitfunction
        self._statusVariables['odmr_2d_high_fitfunction'] = self.odmr_2d_high_fitfunction
        return 0

    def get_hardware_constraints(self):
        """ Retrieve the hardware constraints.

        @return dict: dict with constraints for the magnet hardware. The keys
                      are the labels for the axis and the items are again dicts
                      which contain all the limiting parameters.
        """
        return self._magnet_device.get_constraints()

    def move_rel(self, param_dict):
        """ Move the specified axis in the param_dict relative with an assigned
            value.

        @param dict param_dict: dictionary, which passes all the relevant
                                parameters. E.g., for a movement of an axis
                                labeled with 'x' by 23 the dict should have the
                                form:
                                    param_dict = { 'x' : 23 }
        @return param dict: dictionary, which passes all the relevant
                                parameters. E.g., for a movement of an axis
                                labeled with 'x' by 23 the dict should have the
                                form:
                                    param_dict = { 'x' : 23 }
        """

        self.sigMoveRel.emit(param_dict)
        # self._check_position_reached_loop(start_pos, end_pos)
        # self.sigPosChanged.emit(param_dict)
        return param_dict

    def move_abs(self, param_dict):
        """ Moves stage to absolute position (absolute movement)

        @param dict param_dict: dictionary, which passes all the relevant
                                parameters, which should be changed. Usage:
                                 {'axis_label': <a-value>}.
                                 'axis_label' must correspond to a label given
                                 to one of the axis.

        @return param dict: dictionary, which passes all the relevant
                                parameters. E.g., for a movement of an axis
                                labeled with 'x' by 23 the dict should have the
                                form:
                                    param_dict = { 'x' : 23 }
        """
        # self._magnet_device.move_abs(param_dict)
        # start_pos = self.get_pos(list(param_dict))
        self.sigMoveAbs.emit(param_dict)

        # self._check_position_reached_loop(start_pos, param_dict)

        # self.sigPosChanged.emit(param_dict)
        return param_dict

    def get_pos(self, param_list=None):
        """ Gets current position of the stage.

        @param list param_list: optional, if a specific position of an axis
                                is desired, then the labels of the needed
                                axis should be passed as the param_list.
                                If nothing is passed, then from each axis the
                                position is asked.

        @return dict: with keys being the axis labels and item the current
                      position.
        """

        pos_dict = self._magnet_device.get_pos(param_list)
        return pos_dict

    def get_status(self, param_list=None):
        """ Get the status of the position

        @param list param_list: optional, if a specific status of an axis
                                is desired, then the labels of the needed
                                axis should be passed in the param_list.
                                If nothing is passed, then from each axis the
                                status is asked.

        @return dict: with the axis label as key and  a tuple of a status
                     number and a status dict as the item.
        """
        status = self._magnet_device.get_status(param_list)
        return status

    def stop_movement(self):
        """ Stops movement of the stage. """
        self._stop_measure = True
        self.sigAbort.emit()
        return self._stop_measure

    def set_velocity(self, param_dict):
        """ Write new value for velocity.

        @param dict param_dict: dictionary, which passes all the relevant
                                parameters, which should be changed. Usage:
                                 {'axis_label': <the-velocity-value>}.
                                 'axis_label' must correspond to a label given
                                 to one of the axis.
        """
        self.sigVelChanged.emit()
        # self._magnet_device.set_velocity(param_dict)
        return param_dict
