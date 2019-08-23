"""Experimental control script for Zaber rotation motors at Warwick
    Currently untested and unstable - DO NOT USE
    Contact Guy Stimpson for details"""

import time
import serial
from collections import OrderedDict

from core.module import Base, ConfigOption
from interface.motor_interface import MotorInterface


class ZaberRotation(Base, MotorInterface):
    _modclass = 'MotorRotation'
    _modtype = 'hardware'

    _com_port_rot = ConfigOption('com_port_zaber', 'COM7', missing='warn')
    _rot_baud_rate = ConfigOption('zaber_baud_rate', 115200, missing='warn')
    _rot_timeout = ConfigOption('zaber_timeout', 5000, missing='warn')  # TIMEOUT shorter?
    _rot_term_char = ConfigOption('zaber_term_char', '\n', missing='warn')

    _axis_label = ConfigOption('zaber_axis_label', 'phi', missing='warn')
    _min_angle = ConfigOption('zaber_angle_min', -1e5, missing='warn')
    _max_angle = ConfigOption('zaber_angle_max', 1e5, missing='warn')
    _min_step = ConfigOption('zaber_angle_step', 1e-5, missing='warn')

    _min_vel = ConfigOption('zaber_velocity_min', 1e-3, missing='warn')
    _max_vel = ConfigOption('zaber_velocity_max', 10, missing='warn')
    _step_vel = ConfigOption('zaber_velocity_step', 1e-3, missing='warn')

    _micro_step_size = ConfigOption('zaber_micro_step_size', 234.375e-6, missing='warn')
    velocity_conversion = ConfigOption('zaber_speed_conversion', 9.375, missing='warn')

    def openPort(self):

        ser = serial.Serial
