import PyDAQmx as daq
import time

# create output task
task = daq.TaskHandle()
daq.DAQmxCreateTask('AomTask', daq.byref(task))
# create output channel and write voltage
daq.DAQmxCreateAOVoltageChan(task, '/Dev1/AO3', 'AomChannel',
                             0, 10, daq.DAQmx_Val_Volts, None)

def setAOM(v):
    daq.DAQmxWriteAnalogScalarF64(task, True, 0.1, v, None)

#
# daq.DAQmxWriteAnalogScalarF64(task, True, 0.1, 5.0, None)
# time.sleep(1)
# daq.DAQmxWriteAnalogScalarF64(task, True, 0.1, 0.0, None)
# time.sleep(1)
# daq.DAQmxWriteAnalogScalarF64(task, True, 0.1, 10.0, None)
# time.sleep(1)
# daq.DAQmxWriteAnalogScalarF64(task, True, 0.1, 10.0, None)
# time.sleep(1)
