import clr
import os
from enum import Enum

basePath = os.path.join(os.environ['ProgramFiles'], 'Thorlabs', 'Kinesis')
dllPath = os.path.join(basePath, 'ThorLabs.MotionControl.KCube.DCServoCLI.dll')
clr.AddReference(dllPath)
import Thorlabs
import System


class Status(Enum):
    OK = 0x00  # <OK - no error.
    InvalidHandle = 0x01  # <Invalid handle.
    DeviceNotFound = 0x02  # <Device not found.
    DeviceNotOpened = 0x03  # <Device not opened.
    IOError = 0x04  # <I/O error.
    InsufficientResources = 0x05  # <Insufficient resources.
    InvalidParameter = 0x06  # <Invalid parameter.
    DeviceNotPresent = 0x07  # <Device not present.
    IncorrectDevice = 0x08  # <Incorrect device.


# <summary> Values that represent THORLABSDEVICE_API. </summary>
class MotorTypes(Enum):
    NotMotor = 0
    DCMotor = 1
    StepperMotor = 2
    BrushlessMotor = 3
    CustomMotor = 100


# <summary> Values that represent Travel Modes. </summary>
class TravelModes(Enum):
    TravelModeUndefined = 0x00  # <Undefined
    Linear = 0x01  # <Linear travel default units are millimeters
    Rotational = 0x02  # <Rotational travel default units are degrees


# <summary> Values that represent Travel Modes. </summary>
class TravelDirection(Enum):
    TravelDirectionUndefined = 0x00  # <Undefined
    Forwards = 0x01  # <Move in a Forward direction
    Backwards = 0x02  # <Move in a Backward / Reverse direction


# <summary> Values that represent Limit Switch Directions. </summary>
class HomeLimitSwitchDirection(Enum):
    LimitSwitchDirectionUndefined = 0x00  # <Undefined
    ReverseLimitSwitch = 0x01  # <Limit switch in forward direction
    ForwardLimitSwitch = 0x04  # <Limit switch in reverse direction


# <summary> Values that represent Direction Type. </summary>
class DirectionSense(Enum):
    Normal = 0x00  # <Move / Jog direction is normal (clockwise).
    Reverse = 0x01  # <Move / Jog direction is reversed (anti clockwise).


# <summary> Values that represent the motor Jog Modes. </summary>
class JogModes(Enum):
    JogModeUndefined = 0x00  # <Undefined
    Continuous = 0x01  # <Continuous jogging
    SingleStep = 0x02  # <Jog 1 step at a time


# <summary> Values that represent the motor Jog Modes. </summary>
class StopModes(Enum):
    StopModeUndefined = 0x00  # <Undefined
    Immediate = 0x01  # <Stops immediate
    Profiled = 0x02  # <Stops using a velocity profile


# <summary> Value that represent action to be taken when motor hits a limit switch. </summary>
class LimitSwitchModes(Enum):
    LimitSwitchModeUndefined = 0x00  # <Undefined
    LimitSwitchIgnoreSwitch = 0x01  # <Ignore limit switch
    LimitSwitchMakeOnContact = 0x02  # <Switch makes on contact
    LimitSwitchBreakOnContact = 0x03  # <Switch breaks on contact
    LimitSwitchMakeOnHome = 0x04  # <Switch makes on contact when homing
    LimitSwitchBreakOnHome = 0x05  # <Switch breaks on contact when homing
    PMD_Reserved = 0x06  # <Reserved for PMD brushless servo controllers
    LimitSwitchIgnoreSwitchSwapped = 0x81  # <Ignore limit switch (swapped)
    LimitSwitchMakeOnContactSwapped = 0x82  # <Switch makes on contact (swapped)
    LimitSwitchBreakOnContactSwapped = 0x83  # <Switch breaks on contact (swapped)
    LimitSwitchMakeOnHomeSwapped = 0x84  # <Switch makes on contact when homing (swapped)
    LimitSwitchBreakOnHomeSwapped = 0x85  # <Switch breaks on contact when homing (swapped)


# <summary> Value that represent action to be taken when motor hits a limit switch. </summary>
class LimitSwitchSWModes(Enum):
    LimitSwitchSWModeUndefined = 0x00  # <Undefined
    LimitSwitchIgnored = 0x01  # <Ignore limit switch
    LimitSwitchStopImmediate = 0x02  # <Stop immediately when hitting limit switch
    LimitSwitchStopProfiled = 0x03  # <Stop profiled when hitting limit switch
    LimitSwitchIgnored_Rotational = 0x81  # <Ignore limit switch (rotational stage)
    LimitSwitchStopImmediate_Rotational = 0x82  # <Stop immediately when hitting limit switch (rotational stage)
    LimitSwitchStopProfiled_Rotational = 0x83  # <Stop profiled when hitting limit switch (rotational stage)


# <summary> Values that represent LimitsSoftwareApproachPolicy. </summary>
class LimitsSoftwareApproachPolicy(Enum):
    DisallowIllegalMoves = 0  # <Disable any move outside travel range
    AllowPartialMoves = 1  # <Truncate all moves beyond limit to limit.
    AllowAllMoves = 2 # <Allow all moves illegal or not


# <summary> Values that represent Joystick Direction Sense. </summary>
class JoystickDirectionSense(Enum):
    JS_Positive = 0x01  # < Move at constant velocity
    JS_Negative = 0x02  # < Phase B


# <summary> Values that represent the Joystick Mode. </summary>
class JoyStickMode(Enum):
    JS_Velocity = 0x01  # < Move at constant velocity
    JS_Jog = 0x02  # < Phase B
    JS_MoveAbsolute = 0x03  # < Phase A and B


# <summary> Values that represent Trigger Port Mode. </summary>
class TriggerPortMode(Enum):
    TrigDisabled = 0x00  # < Trigger Disabled
    TrigIn_GPI = 0x01  # < General purpose logic input (<see cref="CC_GetStatusBits(const char * serialNo)"> GetStatusBits</see>)
    TrigIn_RelativeMove = 0x02  # < Move relative using relative move parameters
    TrigIn_AbsoluteMove = 0x03  # < Move absolute using absolute move parameters
    TrigIn_Home = 0x04  # < Perform a Home action
    TrigOut_GPO = 0x0A  # < General purpose output (<see cref="CC_SetDigitalOutputs(const char * serialNo byte outputBits)"> SetDigitalOutputs</see>)
    TrigOut_InMotion = 0x0B  # < Set when device moving
    TrigOut_AtMaxVelocity = 0x0C  # < Set when at max velocity
    TrigOut_AtPositionSteps = 0x0D  # < Set when at predefine position steps<br />Set using wTrigStartPos wTrigInterval wTrigNumPulseswTrigPulseWidth
    TrigOut_Synch = 0x0E  # < TBD ?


# <summary> Values that represent Trigger Port Polarity. </summary>
class TriggerPortPolarity(Enum):
    TrigPolarityHigh = 0x01  # < Trigger Polarity high
    TrigPolarityLow = 0x02  # < Trigger Polarity Low


# <summary> Values that represent DeviceMessageClass message types. </summary>
class MovementModes(Enum):
    LinearRange = 0x00  # < Fixed Angular Range defined by MinPosition and MaxPosition
    RotationalUnlimited = 0x01  # < Unlimited angle
    RotationalWrapping = 0x02  # < Angular Range 0 to 360 with wrap around


# <summary> Values that represent DeviceMessageClass message types. </summary>
class MovementDirections(Enum):
    Quickest = 0x00  # < Uses the shortest travel between two angles
    Forwards = 0x01  # < Only rotate in a forward direction
    Reverse = 0x02  # < Only rotate in a backward direction


class DeviceTypes(Enum):
    BenchtopBrushlessMotor = 73
    BenchtopNanoTrak = 22
    BenchtopPiezo_1channel = 41
    BenchtopPiezo_3channel = 71
    BenchtopStepperMotor_1channel = 40
    BenchtopStepperMotor_3channel = 70
    FilterFlipper = 37
    FilterWheel = 47
    KCubeBrushlessMotor = 28
    KCubeDCServo = 27
    KCubeInertialMotor = 97
    KCubeLaserSource = 56
    KCubeNanoTrak = 57
    KCubePiezo = 29
    KCubeSolenoid = 68
    KCubeStepperMotor = 26
    LongTravelStage = 45
    CageRotator = 55
    LabJack490 = 46
    LabJack050 = 49
    ModularNanoTrak = 52
    ModularPiezo = 51
    ModularStepperMotor = 50
    TCubeBrushlessMotor = 67
    TCubeDCServo = 83
    TCubeInertialMotor = 65
    TCubeLaserSource = 86
    TCubeLaserDiode = 64
    TCubeNanoTrak = 82
    TCubeQuad = 89
    TCubeSolenoid = 85
    TCubeStepperMotor = 80
    TCubeStrainGauge = 84
    TCubeTEC = 87
    VerticalStage = 24

def _hardware_type_from_serial(serial_number):
    return DeviceTypes(int(serial_number[0:2]))

def list_available_devices():
    """
    Lists all devices connected to the computer.

    Returns
    -------
    out : dictionary
        dictionary of stage types associated with the attached serial numbers
    """
    Thorlabs.MotionControl.DeviceManagerCLI.DeviceManagerCLI.BuildDeviceList()
    serial_numbers = list(Thorlabs.MotionControl.DeviceManagerCLI.DeviceManagerCLI.GetDeviceList())
    devices = dict()
    for serial_number in serial_numbers:
        device_type = _hardware_type_from_serial(serial_number)
        if device_type in devices.keys():
            devices[device_type].append(serial_number)
        else:
            devices[device_type] = [serial_number]

    return devices


class KDC101Motor:
    """
    Class to control a Thorlabs KDC101 device via the Kinesis API.
    Primary improvement over straightforward APT control is that:
        - doesn't require ActiveX (though does rely on .NET)
        - gives access to advanced features of new hardware e.g. triggering on KDC101 etc

    TODO: Have not wrapped all methods in Kinesis. Doesn't appear that a single class will be able to
    wrap all different devices adequately - may need a base class and different classes for different
    types.

    Parameters
    ----------
    serial_number : int
        Serial number identifying device
    """
    def __init__(self, serial_number):
        self._serial_number = serial_number
        device_type = _hardware_type_from_serial(self._serial_number)
        if device_type != DeviceTypes.KCubeDCServo:
            raise Exception ('Class can only be used to control KDC101 devices')

        # initialize device
        self._device = Thorlabs.MotionControl.KCube.DCServoCLI.KCubeDCServo.CreateKCubeDCServo(self._serial_number)
        self._device.Connect(self._serial_number)

        if not self._device.IsSettingsInitialized():
            self._device.WaitForSettingsInitialized(5000)

        self._motor_configuration = self._device.LoadMotorConfiguration(self._serial_number)
        self._device_settings = self._device.MotorDeviceSettings

    @property
    def serial_number(self):
        """
        Returns the serial number of the motor.

        Returns
        -------
        out : int
            serial number
        """
        return self._serial_number

    @property
    def hardware_info(self):
        """
        Returns hardware information about the motor.

        Returns
        -------
        out : tuple
            (model, software version, hardware version)

        See also
        --------
        hardware_info
        """
        device_info = self._device.GetDeviceInfo()
        return device_info.Name, device_info.SoftwareVersion.ToString(), device_info.HardwareVersion

    @property
    def _status_bits(self):
        """
        Returns status bits of motor

        Returns
        -------
        out : int
            status bits
        """
        self._device.RequestStatusBits()
        status_bits = self._device.GetStatusBits()
        return status_bits

    @property
    def is_forward_hardware_limit_switch_active(self):
        """
        Returns whether forward hardware limit switch is active.
        """
        status_bits = self._status_bits
        mask = 0x00000001
        return bool(status_bits & mask)

    @property
    def is_reverse_hardware_limit_switch_active(self):
        """
        Returns whether reverse hardware limit switch is active.
        """
        status_bits = self._status_bits
        mask = 0x00000002
        return bool(status_bits & mask)

    @property
    def is_in_motion(self):
        """
        Returns whether motor is in motion.
        """
        status_bits = self._status_bits
        mask = 0x00000010 | 0x00000020 | 0x00000040 | 0x00000080 | 0x00000200
        return bool(status_bits & mask)

    @property
    def has_homing_been_completed(self):
        """
        Returns whether homing has been completed at some point.
        """
        status_bits = self._status_bits
        mask = 0x00000400
        return bool(status_bits & mask)

    @property
    def is_tracking(self):
        """
        Returns whether motor is tracking.
        """
        status_bits = self._status_bits
        mask = 0x00001000
        return bool(status_bits & mask)

    @property
    def is_settled(self):
        """
        Returns whether motor is settled.
        """
        status_bits = self._status_bits
        mask = 0x00002000
        return bool(status_bits & mask)

    @property
    def motor_current_limit_reached(self):
        """
        Return whether current limit of motor has been reached.
        """
        status_bits = self._status_bits
        mask = 0x01000000
        return bool(status_bits & mask)

    @property
    def motion_error(self):
        """
        Returns whether there is a motion error (= excessing position error).
        """
        status_bits = self._status_bits
        mask = 0x00004000
        return bool(status_bits & mask)

    @property
    def is_channel_enabled(self):
        """
        Return whether active channel is enabled.

        See also
        --------
        active_channel
        """
        status_bits = self._status_bits
        mask = 0x80000000
        return bool(status_bits & mask)

    @property
    def active_channel(self):
        """
        Active channel number. Used with motors having more than 1 channel.

        CHAN1_INDEX = 0 : channel 1
        CHAN2_INDEX = 1 : channel 2
        """
        return self._active_channel

    def enable(self):
        """
        Enables the motor (the active channel).
        """
        self._device.EnableDevice()

    def disable(self):
        """
        Disables the motor (the active channel).
        """
        self._device.DisableDevice()

    def identify(self):
        """
        Flashes the 'Active' LED at the motor to identify it.
        """
        self._device.IdentifyDevice()

    def get_velocity_parameters(self):
        """
        Returns current velocity parameters.

        Returns
        -------
        out : tuple
            (minimum velocity, acceleration, maximum velocity)
        """
        vel_params = self._device.GetVelocityParams()
        return float(str(vel_params.MinVelocity)),\
               float(str(vel_params.Acceleration)),\
               float(str(vel_params.MaxVelocity))

    def set_velocity_parameters(self, min_vel, accn, max_vel):
        """
        Sets velocity parameters. According to the Thorlabs documentation
        minimum velocity is always 0 and hence is ignored.

        Parameters
        ----------
        min_vel : float
            minimum velocity
        accn : float
            acceleration
        max_vel : float
            maximum velocity
        """
        vel_params = Thorlabs.MotionControl.GenericMotorCLI.ControlParameters.VelocityParameters()
        vel_params.MinVelocity = System.Decimal(min_vel)
        vel_params.Acceleration = System.Decimal(accn)
        vel_params.MaxVelocity = System.Decimal(max_vel)
        self._device.SetVelocityParams(vel_params)

    def get_move_home_parameters(self):
        """
        Returns parameters used when homing.

        Returns
        -------
        out : tuple
            (direction, limiting switch, velocity, zero offset)
        """
        homing_params = self._device.GetHomingParams()
        return homing_params.Direction,\
                   homing_params.LimitSwitch,\
                   float(str(homing_params.Velocity)),\
                   float(str(homing_params.OffsetDistance))

    def set_move_home_parameters(self, direction, lim_switch, velocity,
            zero_offset):
        """
        Sets parameters used when homing.

        Parameters
        ----------
        direction : int
            home in forward or reverse direction:
            - HOME_FWD = 1 : Home in the forward direction.
            - HOME_REV = 2 : Home in the reverse direction.
        lim_switch : int
            forward limit switch or reverse limit switch:
            - IGNORE = 1;
            - CLOCKWISEHARD = 2; Irrelevant for KDC101
            - COUNTERCLOCKWISEHARD = 3; Irrelevant for KDC101
        velocity : float
            velocity of the motor
        zero_offset : float
            zero offset
        """
        home_params = Thorlabs.MotionControl.GenericMotorCLI.ControlParameters.HomeParameters()
        home_params.Direction = direction
        home_params.LimitSwitch = lim_switch
        home_params.Velocity = System.Decimal(velocity)
        home_params.OffsetDistance = System.Decimal(zero_offset)
        self._device.SetHomingParams(home_params)

    def get_limit_switch_parameters(self):
        """
        Get the limit switch parameters for the controller

        Returns
        --------
        (anticlockwise_limit, clockwise_limit, anticlockwise_hardware_limit, clockwise_hardware_limit)
        """
        lim_switch_params = self._device.GetLimitSwitchParams()
        return float(str(lim_switch_params.AnticlockwisePosition)),\
            float(str(lim_switch_params.ClockwisePosition)),\
            LimitSwitchModes(lim_switch_params.AnticlockwiseHardwareLimit),\
            LimitSwitchModes(lim_switch_params.ClockwiseHardwareLimit)

    def get_travel_limits(self):
        """
        Get the travel limits in real-world units

        Returns
        --------
        (minimum_limit, maximum_limit)
        """
        motor_limits = self._device.AdvancedMotorLimits
        return float(str(motor_limits.LengthMinimum)), float(str(motor_limits.LengthMaximum))

    def move_to(self, absolute_position, timeout = 0):
        """
        Move to absolute position.

        Parameters
        ----------
        absolute_position : float
            absolute position to move to
        timeout : int
            timeout in ms
        """
        self._device.MoveTo(System.Decimal(absolute_position), timeout)

    def move_by(self, relative_position, timeout = 0):
        """
        Move relative to current position.

        Parameters
        ----------
        relative_position : float
            relative distance in mm
        timeout : int
            timeout in ms
        """

        if relative_position < 0:
            direction = 2
        else:
            direction = 1
        self._device.MoveRelative(direction, System.Decimal(relative_position), timeout)

    @property
    def position(self):
        """
        Position of motor. Setting the position is absolute and non-blocking.
        """
        position = self._device.Position
        return float(str(position))

    @position.setter
    def position(self, absolute_position):
        self.move_to(absolute_position)

    def move_home(self, timeout=0):
        """
        Move to home position.

        Parameters
        ----------
        timeout : int
            timeout to wait for command to complete (0 [default] is return instantly)
        """
        self._device.Home(timeout)

    def move_continuously(self, direction):
        """
        Parameters
        ----------
        direction : int
            MOVE_FWD = 1 : Move forward
            MOVE_REV = 2 : Move reverse
        """
        self._device.MoveContinuous(direction)

    def stop_profiled(self, timeout=0):
        """
        Stop motor but turn down velocity slowly (profiled).
        Parameters
        ----------
        timeout : int
            timeout to wait for command to complete (0 [default] is return instantly)
        """
        self._device.Stop(timeout)

    def set_trigger_parameters(self, trigger_num, trig_mode, trig_polarity):
        """
        Set trigger parameters for the given trigger number; all other trigger settings
        will remain the same

        Parameters
        ----------
        trigger_num : int
            Which trigger to modify (1 or 2)
        trig_mode : TriggerPortMode
        trig_polarity : TriggerPortPolarity
        """
        trig_mode = trig_mode.value
        trig_polarity = trig_polarity.value

        trigger_params = self._device.GetTriggerConfigParams()
        if trigger_num == 1:
            trigger_params.Trigger1Mode = trig_mode
            trigger_params.Trigger1Polarity = trig_polarity
        else:
            trigger_params.Trigger2Mode = trig_mode
            trigger_params.Trigger2Polarity = trig_polarity

        self._device.SetTriggerConfigParams(trigger_params)

    def get_trigger_parameters(self, trigger_channel):
        """
        Retrieve the trigger config parameters for the given trigger channel

        Parameters
        ----------
        trigger_channel : int
            Number of the trigger channel for which to retrieve the config params (1 or 2)

        Returns
        ----------
        (trig_mode, trig_polarity)

        trig_mode : TriggerPortMode
        trig_polarity : TriggerPortPolarity
        """
        trigger_params = self._device.GetTriggerConfigParams()
        if trigger_channel == 1:
            mode = trigger_params.Trigger1Mode
            polarity = trigger_params.Trigger1Polarity
        else:
            mode = trigger_params.Trigger2Mode
            polarity = trigger_params.Trigger2Polarity

        return TriggerPortMode(mode), TriggerPortPolarity(polarity)

    def set_relative_move_distance(self, relative_distance_to_move):
        """
        Set the relative move parameters for later hardware triggering
        """
        self._device.SetMoveRelativeDistance(System.Decimal(relative_distance_to_move))

    def get_relative_move_distance(self):
        """
        Get the relative move distance for later hardware triggering
        """
        return float(str(self._device.GetMoveRelativeDistance()))

    def set_absolute_move_postion(self, absolute_position_to_move_to):
        """
        Sets the absolute position to move to on a later hardware trigger

        Parameters
        ----------
        absolute_position_to_move_to : float
            The absolute position (in mm) to move to
        """
        self._device.SetMoveAbsolutePosition(System.Decimal(absolute_position_to_move_to))

    def get_absolute_move_postion(self):
        """
        Gets the absolute position to move to on a later hardware trigger
        """
        return float(str(self._device.GetMoveAbsolutePosition()))

    def disconnect(self):
        self._device.Disconnect()