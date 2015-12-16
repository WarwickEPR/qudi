# -*- coding: utf-8 -*-


from hardware.fast_counter_interface import FastCounterInterface
from core.base import Base
import numpy as np
import thirdparty.opal_kelly as ok
import struct

class FastCounterFPGAQO(Base, FastCounterInterface):
    """ unstable: Nikolas Tomek
        This is the hardware class for the Spartan-6 (Opal Kelly XEM6310) FPGA based fast counter.
    """
    _modclass = 'fastcounter_fpga_qo'
    _modtype = 'hardware'
    # declare connectors
    _out = {'fastcounter': 'FastCounterInterface'}

    def __init__(self, manager, name, config = {}, **kwargs):
        callback_dict = {'onactivate': self.activation, 'ondeactivate': self.deactivation}
        Base.__init__(self, manager, name, config, callback_dict, **kwargs)

    def activation(self, e):
        config = self.getConfiguration()
        if 'fpgacounter_serial' in config.keys():
            self._serial=config['fpgacounter_serial']
        else:
            self.logMsg('No serial number defined for fpga counter', msgType='warning')

        # create an instance of the Opal Kelly FrontPanel
        self._fpga = ok.FrontPanel()
        # fast counter state
        self.statusvar = -1
        # fast counter parameters to be configured. Default values.
        self._binwidth = 1              # number of elementary bins to be put together in one bigger bin
        self._gate_length_bins = 8192   # number of bins in one gate (max 8192)
        self._number_of_gates = 1       # number of gates in the pulse sequence (max 2048)
        self._histogram_size = 1*8192     # histogram size in bins to tell the FPGA (integer multiple of 8192)

        self._old_data = None           # histogram to be added to the current data, i.e. after an overflow on the FPGA.
        self._overflown = False         # overflow indicator
        self.count_data = None
        # connect to the FPGA module
        self._connect()     

    def deactivation(self, e):
        self.stop_measure()
        self.statusvar = 0

    def _connect(self):
        """ This method connects this host PC to the FPGA module with the specified serial number
        """
        # check if a FPGA is connected to this host PC
        if not self._fpga.GetDeviceCount():
            self.logMsg('No FPGA connected to host PC or FrontPanel.exe is running', msgType='error')
            return -1
        # open a connection to the FPGA with the specified serial number
        self._fpga.OpenBySerial(self._serial)
        # upload the fast counter configuration bitfile to the FPGA
        self._fpga.ConfigureFPGA('C:\\software\\qudi\\trunk\\hardware\\fastcounter_top.bit')
        # check if the upload was successful and the Opal Kelly FrontPanel is enabled on the FPGA
        if not self._fpga.IsFrontPanelEnabled():
            self.logMsg('Opal Kelly FrontPanel is not enabled in FPGA', msgType='error')
            self.statusvar = -1
            return -1
        else:
            # put the fast counter logic and its clock into reset mode
            self._fpga.SetWireInValue(0x00, 0xC0000000)
            self._fpga.UpdateWireIns()
            self.statusvar = 0
        return 0

    def configure(self, bin_width_ns, record_length_ns, number_of_gates = 0):
        """
        Configuration of the fast counter.
        bin_width_ns: Length of a single time bin in the time trace histogram in nanoseconds.
        record_length_ns: Total length of the timetrace/each single gate in nanoseconds.
        number_of_gates: Number of gates in the pulse sequence. Ignore for ungated counter.
        """
        # set class variables
        self._binwidth = int(np.rint(bin_width_ns * 950 / 1000))
        self._gate_length_bins = int(np.rint(record_length_ns / bin_width_ns))
        self._number_of_gates = number_of_gates
        self._histogram_size = number_of_gates * 8192
        # reset overflow indicator
        self._overflown = False
        # release the fast counter clock but leave the logic in reset mode
        # set histogram size in the hardware
        self._fpga.SetWireInValue(0x00, 0x40000000 + self._histogram_size)
        self._fpga.UpdateWireIns()
        self.statusvar = 1
        return 0
        
    def start_measure(self):
        """
        Starts the fast counter.
        """
        # initialize the data array
        self.count_data = np.zeros([self._number_of_gates, self._gate_length_bins])
        # reset overflow indicator
        self._overflown = False
        # release all reset states and start the counter. Keep the histogram size.
        self._fpga.SetWireInValue(0x00, self._histogram_size)
        self._fpga.UpdateWireIns()
        self.statusvar = 2
        return 0
        
    def get_data_trace(self):
        """
        Polls the current timetrace data from the fast counter and returns it as a numpy array (dtype = int64).
        The binning specified by calling configure() must be taken care of in this hardware class.
        A possible overflow of the histogram bins must be caught here and taken care of.
        If the counter is UNgated it will return a 1D-numpy-array with returnarray[timebin_index]
        If the counter is gated it will return a 2D-numpy-array with returnarray[gate_index, timebin_index]
        """
        # initialize the read buffer for the USB transfer.
        # one timebin of the data to read is 32 bit wide and the data is transfered in bytes
        data_buffer = bytearray(self._histogram_size*4)
        # check if the timetagger had an overflow.
        self._fpga.UpdateWireOuts()
        flags = self._fpga.GetWireOutValue(0x20)
        if flags != 0:
            # send acknowledge signal to FPGA
            self._fpga.SetWireInValue(0x00, 0x8000000 + self._histogram_size)
            self._fpga.UpdateWireIns()
            self._fpga.SetWireInValue(0x00, self._histogram_size)
            self._fpga.UpdateWireIns()
            # save latest count data into a new class variable to preserve it
            self._old_data = self.count_data.copy()
            self._overflown = True
        # trigger the data read in the FPGA
        self._fpga.SetWireInValue(0x00, 0x20000000 + self._histogram_size)
        self._fpga.UpdateWireIns()
        self._fpga.SetWireInValue(0x00, self._histogram_size)
        self._fpga.UpdateWireIns()
        # read data from the FPGA
        self._fpga.ReadFromBlockPipeOut(0xA0, 1024, data_buffer)
        # encode the bytearray data into 32-bit integers
        buffer_encode = np.array(struct.unpack("<"+"L"*self._histogram_size, data_buffer))
        # bin the data according to the specified bin width
        if self._binwidth != 1:
            buffer_encode = buffer_encode[:(buffer_encode.size // self._binwidth) * self._binwidth].reshape(-1, self._binwidth).sum(axis=1)
        # reshape the data array into the 2D output array    
        self.count_data = buffer_encode.reshape(-1, self._number_of_gates)[:, 0:self._gate_length_bins]
        if self._overflown:
            self.count_data = np.add(self.count_data, self._old_data)
        return self.count_data

    def stop_measure(self):
        """
        Stops the fast counter.
        """
        # put the fast counter logic into reset state
        self._fpga.SetWireInValue(0x00, 0x40000000 + self._histogram_size)
        self._fpga.UpdateWireIns()
        # reset overflow indicator
        self._overflown = False
        self.statusvar = 1
        return 0
        
    def pause_measure(self):
        """
        Pauses the current measurement if the fast counter is in running state.
        """
        # set the pause state in the FPGA
        self._fpga.SetWireInValue(0x00, 0x10000000 + self._histogram_size)
        self._fpga.UpdateWireIns()
        self.statusvar = 3
        return 0
        
    def continue_measure(self):
        """
        Continues the current measurement if the fast counter is in pause state.
        """
        # exit the pause state in the FPGA
        self._fpga.SetWireInValue(0x00, self._histogram_size)
        self._fpga.UpdateWireIns()
        self.statusvar = 2
        return 0
        
    def is_gated(self):
        """
        Boolean return value indicates if the fast counter is a gated counter (TRUE) or not (FALSE).
        """
        return True

    def get_binwidth(self):
        """
        returns the width of a single timebin in the timetrace in seconds
        """
        width_in_seconds = self._binwidth * 1e6/950
        return width_in_seconds

    def get_status(self):
        """
        Receives the current status of the Fast Counter and outputs it as return value.
        0 = unconfigured
        1 = idle
        2 = running
        3 = paused
        -1 = error state
        """
        return self.statusvar