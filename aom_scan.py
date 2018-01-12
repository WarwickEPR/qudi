import PyDAQmx as daq
import time
import sys

# create output task
task = daq.TaskHandle()
daq.DAQmxCreateTask('AomTask', daq.byref(task))

clkTask = daq.TaskHandle()

clock_channel = '/Dev1/Ctr0'
counter_channel = '/Dev1/Ctr1'
scanner_clock_channel = '/Dev1/Ctr2'
scanner_counter_channel = '/Dev1/Ctr3'
photon_source = '/Dev1/PFI8'

clock_frequency = 100


def setup_clock():
    try:
        # create task for clock
        task_name = 'PsatClock'
        daq.DAQmxCreateTask(task_name, daq.byref(clkTask))

        # create a digital clock channel with specific clock frequency:
        daq.DAQmxCreateCOPulseChanFreq(
            # The task to which to add the channels
            clkTask,
            # which channel is used?
            clock_channel,
            # Name to assign to task (NIDAQ uses by # default the physical channel name as
            # the virtual channel name. If name is specified, then you must use the name
            # when you refer to that channel in other NIDAQ functions)
            'Clock Producer',
            # units, Hertz in our case
            daq.DAQmx_Val_Hz,
            # idle state
            daq.DAQmx_Val_High,
            # initial delay
            0,
            # pulse frequency, divide by 2 such that length of semi period = count_interval
            clock_frequency / 2,
            # duty cycle of pulses, 0.5 such that high and low duration are both
            # equal to count_interval
            0.5)

        # Configure Implicit Timing.
        # Set timing to continuous, i.e. set only the number of samples to
        # acquire or generate without specifying timing:
        daq.DAQmxCfgImplicitTiming(
            # Define task
            clkTask,
            # Sample Mode: set the task to generate a continuous amount of running samples
            daq.DAQmx_Val_ContSamps,
            # buffer length which stores temporarily the number of generated samples
            1000)

        daq.DAQmxStartTask(clkTask)

     except:
        sys.stderr.write('Error while setting up clock.')
        return -1

# create output channel and write voltage
daq.DAQmxCreateAOVoltageChan(task, '/Dev1/AO3', 'AomChannel',
                             0, 10, daq.DAQmx_Val_Volts, None)
daq.DAQmxWriteAnalogScalarF64(task, True, 0.1, 5.0, None)
time.sleep(1)
daq.DAQmxWriteAnalogScalarF64(task, True, 0.1, 0.0, None)
time.sleep(1)
daq.DAQmxWriteAnalogScalarF64(task, True, 0.1, 10.0, None)
time.sleep(1)
daq.DAQmxWriteAnalogScalarF64(task, True, 0.1, 5.0, None)
time.sleep(1)
