import os
from gui.guibase import GUIBase
from qtpy import QtWidgets, QtCore, uic
import pyqtgraph as pg
import time
from gui.guiutils import ColorBar
from gui.colordefs import ColorScaleInferno
from gui.colordefs import QudiPalettePale as palette

from core.module import Connector, ConfigOption


class StepperWindow(QtWidgets.QMainWindow):
    """ Create the Main Window based on the *.ui file. """

    activityChanged = QtCore.Signal(bool)

    def __init__(self):
        # Get the path to the *.ui file
        this_dir = os.path.dirname(__file__)
        ui_file = os.path.join(this_dir, 'steppergui.ui')

        # Load it
        super().__init__()
        uic.loadUi(ui_file, self)
        self.show()

    def changeEvent(self, event):
        if event.type() == QtCore.QEvent.ActivationChange:
            self.activityChanged.emit(self.isActiveWindow())


class Oscillate(QtCore.QThread):
    finished = QtCore.Signal()

    def __init__(self, wobbler):
        QtCore.QThread.__init__(self)
        self.wobbler = wobbler

    def __del__(self):
        self.wait()

    def run(self):
        while not self.isInterruptionRequested():
            self.wobbler.scan_z()
            time.sleep(0.1)
        self.finished.emit()

class StepperGui(GUIBase):
    _modclass = 'StepperGui'
    _modtype = 'gui'

    stepperlogic = Connector(interface='StepperLogic')
    scanlogic = Connector(interface='AttocubeZScanLogic')
    oscillatelogic = Connector(interface='AttocubeZScanLogic')

    x_speed = ConfigOption('x_speed', {"Normal": [30, 100]})  # voltage, frequency
    y_speed = ConfigOption('y_speed', {"Normal": [30, 100]})
    z_speed = ConfigOption('z_speed', {"Normal": [30, 100]})

    def __init__(self, config, **kwargs):
        """Create a TestWindow object.

          @param dict config: configuration dictionary
          @param dict kwargs: further optional arguments
        """
        super().__init__(config=config, **kwargs)
        self._oscillateThread = None

    def on_activate(self):
        """This sets up all the necessary UI elements, initialises and wires user interactions
        """
        self._mw = StepperWindow()
        self._hw = self.get_connector('stepperlogic')
        self._scan = self.get_connector('scanlogic')
        self._wobble = self.get_connector('oscillatelogic')

        self.speed = dict(x=self.x_speed, y=self.y_speed, z=self.z_speed)

        # set initial values
        for speed in self.x_speed:
            self._mw.speed_x.addItem(speed)
        self._mw.speed_x.addItem("User set")
        self.set_speed_x("Normal")

        for speed in self.y_speed:
            self._mw.speed_y.addItem(speed)
        self._mw.speed_y.addItem("User set")
        self.set_speed_y("Normal")

        for speed in self.z_speed:
            self._mw.speed_z.addItem(speed)
        self._mw.speed_z.addItem("User set")
        self.set_speed_z("Normal")

        [v_min, v_max] = self._hw.get_voltage_range('x')
        [f_min, f_max] = self._hw.get_frequency_range('y')
        self._mw.voltage_x.setRange(v_min, v_max)
        self._mw.voltage_y.setRange(v_min, v_max)
        self._mw.voltage_z.setRange(v_min, v_max)
        self._mw.frequency_x.setRange(f_min, f_max)
        self._mw.frequency_y.setRange(f_min, f_max)
        self._mw.frequency_z.setRange(f_min, f_max)

        # todo: toggle between stepper and offset mode

        self._mw.activityChanged.connect(lambda x: self.log.info("Activity changed: {}".format(x)))
        self._mw.tabs.currentChanged.connect(self.tab_changed)

        # connect user interaction for movement

        self._mw.step_up_x.clicked.connect(self.step_up_x)
        self._mw.step_up_y.clicked.connect(self.step_up_y)
        self._mw.step_up_z.clicked.connect(self.step_up_z)
        self._mw.step_down_x.clicked.connect(self.step_down_x)
        self._mw.step_down_y.clicked.connect(self.step_down_y)
        self._mw.step_down_z.clicked.connect(self.step_down_z)
        self._mw.buzz_up_x.pressed.connect(self.buzz_up_x)
        self._mw.buzz_up_y.pressed.connect(self.buzz_up_y)
        self._mw.buzz_up_z.pressed.connect(self.buzz_up_z)
        self._mw.buzz_down_x.pressed.connect(self.buzz_down_x)
        self._mw.buzz_down_y.pressed.connect(self.buzz_down_y)
        self._mw.buzz_down_z.pressed.connect(self.buzz_down_z)
        self._mw.buzz_up_x.released.connect(self.stop_x)
        self._mw.buzz_up_y.released.connect(self.stop_y)
        self._mw.buzz_up_z.released.connect(self.stop_z)
        self._mw.buzz_down_x.released.connect(self.stop_x)
        self._mw.buzz_down_y.released.connect(self.stop_y)
        self._mw.buzz_down_z.released.connect(self.stop_z)

        # connect user selection of speed
        self._mw.voltage_x.valueChanged.connect(self.set_voltage_x)
        self._mw.voltage_y.valueChanged.connect(self.set_voltage_y)
        self._mw.voltage_z.valueChanged.connect(self.set_voltage_z)

        self._mw.frequency_x.valueChanged.connect(self.set_frequency_x)
        self._mw.frequency_y.valueChanged.connect(self.set_frequency_y)
        self._mw.frequency_z.valueChanged.connect(self.set_frequency_z)

        self._mw.speed_x.currentIndexChanged.connect(self.set_speed_x_i)
        self._mw.speed_y.currentIndexChanged.connect(self.set_speed_y_i)
        self._mw.speed_z.currentIndexChanged.connect(self.set_speed_z_i)

        # buttons
        self._mw.stop_all.clicked.connect(self.stop_all)
        self._mw.z_scan.clicked.connect(self.run_z_scan)

        # slider
        self._mw.offset_slider.valueChanged.connect(self.offset_changed)

        # oscillations
        self._mw.oscillate.toggled.connect(self.oscillate)

        # initialise in stepping mode
        self._mw.tabs.setCurrentIndex(0)
        self.tab_changed(0)


        self.z_image = pg.PlotDataItem(self._scan.offsets,
                                       self._scan.rates,
                                       pen=pg.mkPen(palette.c1, style=QtCore.Qt.DotLine),
                                       symbol='x',
                                       symbolPen=palette.c1,
                                       symbolBrush=palette.c1,
                                       symbolSize=7)

        # self.z_fit_image = pg.PlotDataItem(self._short_scan_logic.fit_z,
        #                                    self._short_scan_logic.fit_counts,
        #                                    pen=pg.mkPen(palette.c2))

        # Add the display item to the xy and xz ViewWidget, which was defined in the UI file.
        self._mw.z_PlotWidget.addItem(self.z_image)
        self._mw.z_PlotWidget.setLabel(axis='left', text='Counts', units='Counts/s')
        self._mw.z_PlotWidget.setLabel(axis='bottom', text='Offset', units='V')
        self._mw.z_PlotWidget.showGrid(x=True, y=True, alpha=0.8)

    def on_deactivate(self):

        self._mw.activityChanged.disconnect()
        self._mw.step_up_y.clicked.disconnect()
        self._mw.step_up_x.clicked.disconnect()
        self._mw.step_up_z.clicked.disconnect()
        self._mw.step_down_x.clicked.disconnect()
        self._mw.step_down_y.clicked.disconnect()
        self._mw.step_down_z.clicked.disconnect()
        self._mw.buzz_up_x.pressed.disconnect()
        self._mw.buzz_up_y.pressed.disconnect()
        self._mw.buzz_up_z.pressed.disconnect()
        self._mw.buzz_down_x.pressed.disconnect()
        self._mw.buzz_down_y.pressed.disconnect()
        self._mw.buzz_down_z.pressed.disconnect()
        self._mw.buzz_up_x.released.disconnect()
        self._mw.buzz_up_y.released.disconnect()
        self._mw.buzz_up_z.released.disconnect()
        self._mw.buzz_down_x.released.disconnect()
        self._mw.buzz_down_y.released.disconnect()
        self._mw.buzz_down_z.released.disconnect()

        # connect user selection of speed
        self._mw.voltage_x.valueChanged.disconnect()
        self._mw.voltage_y.valueChanged.disconnect()
        self._mw.voltage_z.valueChanged.disconnect()

        self._mw.frequency_x.valueChanged.disconnect()
        self._mw.frequency_y.valueChanged.disconnect()
        self._mw.frequency_z.valueChanged.disconnect()

        self._mw.speed_x.currentIndexChanged.disconnect()
        self._mw.speed_y.currentIndexChanged.disconnect()
        self._mw.speed_z.currentIndexChanged.disconnect()

        self._mw.stop_all.clicked.disconnect()
        self._mw.z_scan.clicked.disconnect()

        self._mw.offset_slider.valueChanged.disconnect()

        self._mw.close()

    def show(self):
        """Make main window visible and put it above all other windows. """
        # Show the Main Confocal GUI:
        self._mw.show()
        self._mw.activateWindow()
        self._mw.raise_()

    def set_speed_edit_enabled(self, axis, state):
        if axis == 'x':
            self._mw.voltage_x.setEnabled(state)
            self._mw.frequency_x.setEnabled(state)
        elif axis == 'y':
            self._mw.voltage_y.setEnabled(state)
            self._mw.frequency_y.setEnabled(state)
        elif axis == 'z':
            self._mw.voltage_z.setEnabled(state)
            self._mw.frequency_z.setEnabled(state)

    def get_speed(self, axis):
        if axis == 'x':
            return self._mw.speed_x.value()
        elif axis == 'y':
            return self._mw.speed_y.value()
        elif axis == 'z':
            return self._mw.speed_z.value()
        else:
            return 'User set'

    def get_user_speed(self, axis):
        if axis == 'x':
            return [self._mw.voltage_x.value(), self._mw.frequency_x.value()]
        elif axis == 'y':
            return [self._mw.voltage_y.value(), self._mw.frequency_y.value()]
        elif axis == 'z':
            return [self._mw.voltage_z.value(), self._mw.frequency_z.value()]
        else:
            return [0.0, 0]

    def set_user_speed_from_hardware(self, axis):
        v = self._hw.get_step_voltage(axis)
        f = self._hw.get_step_frequency(axis)
        if axis == 'x':
            self._mw.voltage_x.setValue(v)
            self._mw.frequency_x.setValue(f)
        elif axis == 'y':
            self._mw.voltage_y.setValue(v)
            self._mw.frequency_y.setValue(f)
        elif axis == 'z':
            self._mw.voltage_z.setValue(v)
            self._mw.frequency_z.setValue(f)

    def set_voltage_x(self, v):
        self._hw.set_step_voltage('x', v)

    def set_voltage_y(self, v):
        self._hw.set_step_voltage('y', v)

    def set_voltage_z(self, v):
        self._hw.set_step_voltage('z', v)

    def set_frequency_x(self, f):
        self._hw.set_step_frequency('x', f)

    def set_frequency_y(self, f):
        self._hw.set_step_frequency('y', f)

    def set_frequency_z(self, f):
        self._hw.set_step_frequency('z', f)

    def set_speed(self, axis, speed):

        self.log.info("Setting speed to {}".format(speed))
        _speed = self.speed[axis]
        if speed == "User set":
            self.set_speed_edit_enabled(axis, True)
            [v, f] = self.get_user_speed(axis)
            self._hw.set_step_voltage(axis, v)
            self._hw.set_step_frequency(axis, f)
        elif speed in _speed:
            # get speed from configuration
            [v, f] = _speed[speed]
            self.set_speed_edit_enabled(axis, False)
            self._hw.set_step_voltage(axis, v)
            self._hw.set_step_frequency(axis, f)
        else:
            self.log.warn("Failed to set speed for axis {} to {}".format(axis, speed))

    def set_mode_for_tab(self, index):
        if index == 1:
            # fine control of z mode
            self._hw.set_axis_mode('z', 'offset')
        else:
            self._he
            self._hw.set_axis_mode('z', 'step')

    def set_speed_x_i(self, i):
        speed = self._mw.speed_x.itemText(i)
        self.set_speed_x(speed)

    def set_speed_y_i(self, i):
        speed = self._mw.speed_y.itemText(i)
        self.set_speed_y(speed)

    def set_speed_z_i(self, i):
        speed = self._mw.speed_z.itemText(i)
        self.set_speed_z(speed)

    def set_speed_x(self, speed):
        self.set_speed('x', speed)

    def set_speed_y(self, speed):
        self.set_speed('y', speed)

    def set_speed_z(self, speed):
        self.set_speed('z', speed)

    def buzz_up_x(self):
        self._hw.step_up_continuously('x')  # continuous until stopped

    def buzz_down_x(self):
        self._hw.step_down_continuously('x')  # continuous until stopped

    def buzz_up_y(self):
        self._hw.step_up_continuously('y')  # continuous until stopped

    def buzz_down_y(self):
        self._hw.step_down_continuously('y')  # continuous until stopped

    def buzz_up_z(self):
        self._hw.step_up_continuously('z')  # continuous until stopped

    def buzz_down_z(self):
        self._hw.step_down_continuously('z')  # continuous until stopped

    def step_up_x(self):
        self._hw.step_up('x', 1)

    def step_down_x(self):
        self._hw.step_down('x', 1)

    def step_up_y(self):
        self._hw.step_up('y', 1)

    def step_down_y(self):
        self._hw.step_down('y', 1)

    def step_up_z(self):
        self._hw.step_up('z', 1)

    def step_down_z(self):
        self._hw.step_down('z', 1)

    def stop_x(self):
        self._hw.stop_axis('x')

    def stop_y(self):
        self._hw.stop_axis('y')

    def stop_z(self):
        self._hw.stop_axis('z')

    def stop_all(self):
        self._hw.stop_all_axes()

    def run_z_scan(self):
        self._scan.scan_z()
        self.z_image.setData(self._scan.offsets, self._scan.rates)

    def wobble(self):
        self._wobble.scan_z()
        # could copy data too, but leave it

    def offset_changed(self):
        n = self._mw.offset_slider.value()
        offset = 60.0 * n/1000.0;
        self._mw.voltage.setText("%.2f" % offset)
        self._hw.set_offset('z', offset)

    def set_offset_from_hardware(self):
        offset = self._hw.get_offset('z')
        n = int(offset / 60.0 * 1000)
        self._mw.offset_slider.setValue(n)
        self.offset_changed()

    def oscillate(self, stopped):
        # oscillate until unchecked`
        self.log.info("Oscillate changed to {}".format(not stopped))
        if not stopped:
            if not self._oscillateThread:
                self._oscillateThread = Oscillate(self._wobble)

            self._oscillateThread.finished.connect(self.oscillate_done)
            self._oscillateThread.start()
        elif self._oscillateThread is not None:
            self._oscillateThread.requestInterruption()

    def oscillate_done(self):
        self._oscillateThread.quit()
        self._oscillateThread.wait()

    def tab_changed(self, tab):
        # check offset mode (of z at least)
        mode_x = self._hw.get_axis_mode('x')
        mode_y = self._hw.get_axis_mode('y')
        mode_z = self._hw.get_axis_mode('z')
        self.log.info("Axis x {}".format(mode_x))

        if tab != 1:
            self._hw.set_offset('z', 0.0)

        if tab == 0:
            if mode_x != 'step' or mode_y != 'step' or mode_z != 'step':
                self.log.info("Switching to stepping mode")
                self._hw.set_axis_mode('x', 'step')
                self._hw.set_axis_mode('y', 'step')
                self._hw.set_axis_mode('z', 'step')
                self.log.info("Axis x after {}".format(mode_x))
        else:
            if mode_z != 'offset':
                self.log.info("Switching 'z' to offset mode")
                self._hw.set_axis_mode('z', 'offset')

        if tab == 1:
            self.set_offset_from_hardware()

