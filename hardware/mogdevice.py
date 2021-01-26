"""
moglabs device class
Simplifies communication with moglabs devices

v1.1: Made compatible with both python2 and python3
v1.0: Initial release

(c) MOGLabs 2016--2019
http://www.moglabs.com/
"""
import time
import socket
import select
from struct import unpack
from collections import OrderedDict
import logging
logger = logging.getLogger('MOG')
CRLF = b'\r\n'

# Handles communication with devices
class MOGDevice:
    def __init__(self,addr,port=None,timeout=1,check=True):
        # is it a COM port?
        if addr.startswith('COM') or addr == 'USB':
            if port is not None: addr = 'COM%d'%port
            addr = addr.split(' ',1)[0]
            self.connection = addr
            self.is_usb = True
        else:
            if not ':' in addr:
                if port is None: port=7802
                addr = '%s:%d'%(addr,port)
            self.connection = addr
            self.is_usb = False
        self.reconnect(timeout,check)
    
    def reconnect(self,timeout=1,check=True):
        "Reestablish connection with unit"
        if hasattr(self,'dev'): self.dev.close()
        if self.is_usb:
            import serial
            try:
                self.dev = serial.Serial(self.connection, baudrate=115200, bytesize=8, parity='N', stopbits=1, timeout=timeout, writeTimeout=0)
            except serial.SerialException as E:
                raise RuntimeError(E.args[0].split(':',1)[0])
        else:
            self.dev = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.dev.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.dev.settimeout(timeout)
            addr, port = self.connection.split(':')
            self.dev.connect((addr,int(port)))
        # check the connection?
        if check:
            try:
                self.info = self.ask(b'help')
            except Exception as E:
                logger.error(str(E))
                raise RuntimeError('Device did not respond to query')

    def cmd(self,cmd):
        "Send the specified command, and check the response is OK"
        resp = self.ask(cmd)
        if resp.startswith(b'OK'):
            return resp
        else:
            raise RuntimeError(resp)
        
    def ask(self,cmd):
        "Send followed by receive"
        # check if there's any response waiting on the line
        self.flush()
        self.send(cmd)
        resp = self.recv().strip()
        if resp.startswith(b'ERR:'):
            raise RuntimeError(resp[4:].strip())
        return resp
        
    def ask_dict(self,cmd):
        "Send a request which returns a dictionary response"
        resp = self.ask(cmd)
        # might start with "OK"
        if resp.startswith(b'OK'): resp = resp[3:].strip()
        # expect a colon in there
        if not b':' in resp: raise RuntimeError('Response to '+repr(cmd)+' not a dictionary')
        # response could be comma-delimited (new) or newline-delimited (old)
        vals = OrderedDict()
        for entry in resp.split(b',' if b',' in resp else b'\n'):
            name, val = entry.split(b':')
            vals[name.strip()] = val.strip()
        return vals
        
    def ask_bin(self,cmd):
        "Send a request which returns a binary response"
        self.send(cmd)
        head = self.recv_raw(4)
        # is it an error message?
        if head == b'ERR:': raise RuntimeError(self.recv().strip())
        datalen = unpack('<L',head)[0]
        data = self.recv_raw(datalen)
        if len(data) != datalen: raise RuntimeError('Binary response block has incorrect length')
        return data
    
    def send(self,cmd):
        "Send command, appending newline if not present"
        if hasattr(cmd,'encode'):  cmd = cmd.encode()
        if not cmd.endswith(CRLF): cmd += CRLF
        self.send_raw(cmd)
    
    def has_data(self,timeout=0):
        if self.is_usb:
            import serial
            try:
                if self.dev.inWaiting(): return True
                if timeout == 0: return False
                time.sleep(timeout)
                return self.dev.inWaiting() > 0
            except serial.SerialException: # will raise an exception if the device is not connected
                return False
        else:
            sel = select.select([self.dev],[],[],timeout)
            return len(sel[0])>0
        
    def flush(self,timeout=0,buffer=256):
        dat = b''
        while self.has_data(timeout):
            dat += self.recv(buffer)
        if len(dat): logger.debug('Flushed'+repr(dat))
        return dat
    
    def recv(self,buffer=256):
        "A somewhat robust multi-packet receive call"
        if self.is_usb:
            data = self.dev.readline(buffer)
            if len(data):
                t0 = self.dev.timeout
                self.dev.timeout = 0 if data.endswith(CRLF) else 0.1
                while True:
                    segment = self.dev.readline(buffer)
                    if len(segment) == 0: break
                    data += segment
                self.dev.timeout = t0
            if len(data) == 0: raise RuntimeError('Timed out')
        else:
            data = self.dev.recv(buffer)
            timeout = 0 if data.endswith(CRLF) else 0.1
            while self.has_data(timeout):
                try:
                    segment = self.dev.recv(buffer)
                except IOError:
                    if len(data): break
                    raise
                data += segment
        logger.debug('<< %d = %s'%(len(data),repr(data)))
        return data
    
    def send_raw(self,cmd):
        "Send, without appending newline"
        if len(cmd) < 256:
            logger.debug('>>'+repr(cmd))
        if self.is_usb:
            return self.dev.write(cmd)
        else:
            return self.dev.send(cmd)
    
    def recv_raw(self,size):
        "Receive exactly 'size' bytes"
        # be pythonic: better to join a list of strings than append each iteration
        parts = []
        while size > 0:
            if self.is_usb:
                chunk = self.dev.read(size)
            else:
                chunk = self.dev.recv(size)
            if len(chunk) == 0:
                break
            parts.append(chunk)
            size -= len(chunk)
        buf = b''.join(parts)
        logger.debug('<< RECV_RAW got %d'%len(buf))
        logger.debug(repr(buf))
        return buf
        
    def set_timeout(self,val = None):
        if self.is_usb:
            old = self.dev.timeout
            if val is not None: self.dev.timeout = val
            return old
        else:
            old = self.dev.gettimeout()
            if val is not None: self.dev.settimeout(val)
            return old

        
def load_script(filename):
    with open(filename,"r") as f:
        for linenum, line in enumerate(f):
            # remove comments
            line = line.split('#',1)[0]
            # trim spaces
            line = line.strip()
            if len(line) == 0: continue
            # return this info
            yield linenum+1, line
