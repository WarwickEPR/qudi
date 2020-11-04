# -*- coding: utf-8 -*-
"""
This file contains the Qudi GUI module for ODMR control.

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
from qtpy import QtWidgets
from qtpy import uic
import numpy as np
import os
import time

from core.connector import Connector
from gui.guibase import GUIBase

class StepperInterfaceMainWindow(QtWidgets.QMainWindow):
    """ The main window for the stepper GUI.
    """

    sigPressKeyBoard = QtCore.Signal(QtCore.QEvent)

    def __init__(self):
        # Get the path to the *.ui file
        this_dir = os.path.dirname(__file__)
        ui_file = os.path.join(this_dir, 'ui_stepper_interface_gui.ui')

        # Load it
        super(StepperInterfaceMainWindow, self).__init__()
        uic.loadUi(ui_file, self)
        self.show()

    def keyPressEvent(self, event):
        """Pass the keyboard press event from the main window further. """
        self.sigPressKeyBoard.emit(event)

class StepperInterfaceGui(GUIBase):
    """
    This is the GUI Class for Stepper control
    """

    _modclass = 'StepperInterfaceGui'
    _modtype = 'gui'

    # declare connectors
    stepperlogic1 = Connector(interface='StepperLogic')

    def __init__(self, config, **kwargs):
        super().__init__(config=config, **kwargs)

    def on_activate(self):
        """ Definition, configuration and initialisation of the Confocal Stepper GUI.

        This init connects all the graphic modules, which were created in the
        *.ui file and configures the event handling between the modules.
        """

        self._stepper_logic = self.stepperlogic1()
        self.initMainUI()

        ########################################################################
        #                       Connect signals                                #
        ########################################################################

        # Show the Main SteppingConfocal GUI:
        self.show()

    def on_deactivate(self):
        """ Reverse steps of activation

        @return int: error code (0:OK, -1:error)
        """
        self._mw.close()
        return 0

    def initMainUI(self):
        """ Definition, configuration and initialisation of the confocal stepper GUI.

        This init connects all the graphic modules, which were created in the
        *.ui file and configures the event handling between the modules.
        Moreover it sets default values.
        """
        # Use the inherited class 'Ui_StepperGuiUI' to create now the GUI element:
        self._mw = StepperInterfaceMainWindow()

        ###################################################################
        #               Configuring the dock widgets                      #
        ###################################################################
        # All our gui elements are dockable, and so there should be no "central" widget.
        self._mw.centralwidget.hide()
        self._mw.setDockNestingEnabled(True)

        # setup a timer to prevent someone asking the hardware to recalibrate during a move
        self._timer = QtCore.QTimer()
        self._timer.timeout.connect(self.reenable_hardware_buttons)

        self.init_hardware_UI()
        self._mw.move_up_button.clicked.connect(self.move_up_clicked)
        self._mw.move_down_button.clicked.connect(self.move_down_clicked)
        self._mw.move_left_button.clicked.connect(self.move_left_clicked)
        self._mw.move_right_button.clicked.connect(self.move_right_clicked)
        self._mw.raise_button.clicked.connect(self.raise_clicked)
        self._mw.lower_button.clicked.connect(self.lower_clicked)
        self._mw.stop_button.clicked.connect(self.stop_clicked)

        self._mw.set_origin_button.clicked.connect(self.set_origin)
        self._mw.measure_capacitance_button.clicked.connect(self.measure_capacitance)

        self._mw.sigPressKeyBoard.connect(self.keyPressEvent)

    def init_hardware_UI(self):
        # Set the range for the spin boxes of the voltage and frequency values:
        constraints = self._stepper_logic.get_constraints()
        (minvol, maxvol) = constraints['x']['voltage']
        self._mw.x_amplitude_doubleSpinBox.setRange(minvol, maxvol)
        (minvol, maxvol) = constraints['y']['voltage']
        self._mw.y_amplitude_doubleSpinBox.setRange(minvol, maxvol)
        (minvol, maxvol) = constraints['z']['voltage']
        self._mw.z_amplitude_doubleSpinBox.setRange(minvol, maxvol)

        (minfreq, maxfreq) = constraints['x']['frequency']
        self._mw.x_frequency_spinBox.setRange(minfreq, maxfreq)
        (minfreq, maxfreq) = constraints['y']['frequency']
        self._mw.y_frequency_spinBox.setRange(minfreq, maxfreq)
        (minfreq, maxfreq) = constraints['z']['frequency']
        self._mw.z_frequency_spinBox.setRange(minfreq, maxfreq)

        # set minimal steps for the current value
        self._mw.x_amplitude_doubleSpinBox.setSingleStep(0.1)
        self._mw.y_amplitude_doubleSpinBox.setSingleStep(0.1)
        self._mw.z_amplitude_doubleSpinBox.setSingleStep(0.1)

        # set unit in spin box
        self._mw.x_amplitude_doubleSpinBox.setSuffix(" V")
        self._mw.y_amplitude_doubleSpinBox.setSuffix(" V")
        self._mw.z_amplitude_doubleSpinBox.setSuffix(" V")

        self._mw.x_frequency_spinBox.setSuffix(" Hz")
        self._mw.y_frequency_spinBox.setSuffix(" Hz")
        self._mw.z_frequency_spinBox.setSuffix(" Hz")

        # connect actions
        self._mw.read_hardware_pushButton.clicked.connect(self.measure_stepper_hardware_values)
        self._mw.update_hardware_pushButton.clicked.connect(self.update_stepper_hardware_values)

        # get current step values
        self.measure_stepper_hardware_values()
        self.measure_capacitance()

    def show(self):
        """Make window visible and put it above all other windows. """
        self._mw.show()
        self._mw.activateWindow()
        self._mw.raise_()
        return

    def keyPressEvent(self, event):
        """ Handles the passed keyboard events from the main window.

        @param object event: qtpy.QtCore.QEvent object.
        """
        if event.key() == QtCore.Qt.Key_Right:
            self.move_right_clicked()
        elif event.key() == QtCore.Qt.Key_Left:
            self.move_left_clicked()
        elif event.key() == QtCore.Qt.Key_Up:
            self.move_up_clicked()
        elif event.key() == QtCore.Qt.Key_Down:
            self.move_down_clicked()
        elif event.key() == QtCore.Qt.Key_PageUp:
            self.raise_clicked()
        elif event.key() == QtCore.Qt.Key_PageDown:
            self.lower_clicked()
        else:
            event.ignore()

    def update_stepper_hardware_values(self):
        self.disable_hardware_buttons()
        self._stepper_logic.set_voltage('x', self._mw.x_amplitude_doubleSpinBox.value())
        self._stepper_logic.set_voltage('y', self._mw.y_amplitude_doubleSpinBox.value())
        self._stepper_logic.set_voltage('z', self._mw.z_amplitude_doubleSpinBox.value())

        self._stepper_logic.set_frequency('x', self._mw.x_frequency_spinBox.value())
        self._stepper_logic.set_frequency('y', self._mw.y_frequency_spinBox.value())
        self._stepper_logic.set_frequency('z', self._mw.z_frequency_spinBox.value())

        if self._mw.z_dcin_checkBox.isChecked() is True:
            self._stepper_logic.enable_DC_input('z')

        axes_to_ground = []
        axes_to_unground = []
        if self._mw.x_grounded_checkBox.isChecked() is True:
            axes_to_ground.append('x')
        else:
            axes_to_unground.append('x')
        if self._mw.y_grounded_checkBox.isChecked() is True:
            axes_to_ground.append('y')
        else:
            axes_to_unground.append('y')
        if self._mw.z_grounded_checkBox.isChecked() is True:
            axes_to_ground.append('z')
        else:
            axes_to_unground.append('z')
        if len(axes_to_ground) != 0:
            self._stepper_logic.ground(axes_to_ground)
        if len(axes_to_unground) != 0:
            self._stepper_logic.unground(axes_to_unground)

        time.sleep(0.5)
        self.measure_stepper_hardware_values()

    def measure_stepper_hardware_values(self):
        self.disable_hardware_buttons()
        parameters = self._stepper_logic.refresh_hardware_status()
        xvals = parameters['x']
        yvals = parameters['y']
        zvals = parameters['z']

        self._mw.x_amplitude_doubleSpinBox.setValue(xvals['voltage'])
        self._mw.y_amplitude_doubleSpinBox.setValue(yvals['voltage'])
        self._mw.z_amplitude_doubleSpinBox.setValue(zvals['voltage'])

        self._mw.x_frequency_spinBox.setValue(xvals['frequency'])
        self._mw.y_frequency_spinBox.setValue(yvals['frequency'])
        self._mw.z_frequency_spinBox.setValue(zvals['frequency'])

        self._mw.x_grounded_checkBox.setChecked(xvals['grounded'])
        self._mw.y_grounded_checkBox.setChecked(yvals['grounded'])
        self._mw.z_grounded_checkBox.setChecked(zvals['grounded'])

        self._mw.z_dcin_checkBox.setChecked(zvals['dci'])
        self.update_positions()
        self.reenable_hardware_buttons()

    def measure_capacitance(self):
        capacitance = self._stepper_logic.measure_capacitance()

        self._mw.x_cap_label.setText(str(int(np.round(1e9 * capacitance[0], 0))))
        self._mw.y_cap_label.setText(str(int(np.round(1e9 * capacitance[1], 0))))
        self._mw.z_cap_label.setText(str(int(np.round(1e9 * capacitance[2], 0))))

    def update_positions(self):
        pos = self._stepper_logic.get_current_location()
        self._mw.x_pos_label.setText(str(pos['x']))
        self._mw.y_pos_label.setText(str(pos['y']))
        self._mw.z_pos_label.setText(str(pos['z']))

    def stop_clicked(self):
        self._stepper_logic.stop()
        self.reenable_hardware_buttons()

    def move_up_clicked(self):
        self._stepper_logic.move_number_of_steps('y', self._mw.y_steps_spinbox.value())
        self.disable_hardware_buttons()
        self.update_positions()
        self._timer.start(1000 * self._mw.y_steps_spinbox.value() / self._mw.y_frequency_spinBox.value())

    def move_down_clicked(self):
        self._stepper_logic.move_number_of_steps('y', -self._mw.y_steps_spinbox.value())
        self.disable_hardware_buttons()
        self.update_positions()
        self._timer.start(1000 * self._mw.y_steps_spinbox.value() / self._mw.y_frequency_spinBox.value())

    def move_left_clicked(self):
        self._stepper_logic.move_number_of_steps('x', -self._mw.x_steps_spinbox.value())
        self.disable_hardware_buttons()
        self.update_positions()
        self._timer.start(1000 * self._mw.x_steps_spinbox.value() / self._mw.x_frequency_spinBox.value())

    def move_right_clicked(self):
        self._stepper_logic.move_number_of_steps('x', self._mw.x_steps_spinbox.value())
        self.disable_hardware_buttons()
        self.update_positions()
        self._timer.start(1000 * self._mw.x_steps_spinbox.value() / self._mw.x_frequency_spinBox.value())

    def raise_clicked(self):
        self._stepper_logic.move_number_of_steps('z', self._mw.z_steps_spinbox.value())
        self._mw.z_dcin_checkBox.setChecked(False) # we automatically disable the DC input when we step Z
        self.disable_hardware_buttons()
        self.update_positions()
        self._timer.start(1000 * self._mw.z_steps_spinbox.value() / self._mw.z_frequency_spinBox.value())

    def lower_clicked(self):
        self._stepper_logic.move_number_of_steps('z', -self._mw.z_steps_spinbox.value())
        self._mw.z_dcin_checkBox.setChecked(False)  # we automatically disable the DC input when we step Z
        self.disable_hardware_buttons()
        self.update_positions()
        self._timer.start(1000 * self._mw.z_steps_spinbox.value() / self._mw.z_frequency_spinBox.value())

    def reenable_hardware_buttons(self):
        self._timer.stop()
        self._mw.read_hardware_pushButton.setEnabled(True)
        self._mw.update_hardware_pushButton.setEnabled(True)

        if self._mw.x_grounded_checkBox.isChecked() is False:
            self._mw.move_left_button.setEnabled(True)
            self._mw.move_right_button.setEnabled(True)

        if self._mw.y_grounded_checkBox.isChecked() is False:
            self._mw.move_up_button.setEnabled(True)
            self._mw.move_down_button.setEnabled(True)

        if self._mw.z_grounded_checkBox.isChecked() is False:
            self._mw.raise_button.setEnabled(True)
            self._mw.lower_button.setEnabled(True)

    def disable_hardware_buttons(self):
        self._mw.read_hardware_pushButton.setEnabled(False)
        self._mw.update_hardware_pushButton.setEnabled(False)
        self._mw.move_up_button.setEnabled(False)
        self._mw.move_down_button.setEnabled(False)
        self._mw.move_left_button.setEnabled(False)
        self._mw.move_right_button.setEnabled(False)
        self._mw.raise_button.setEnabled(False)
        self._mw.lower_button.setEnabled(False)

    def set_origin(self):
        self._stepper_logic.set_origin()
        self.update_positions()