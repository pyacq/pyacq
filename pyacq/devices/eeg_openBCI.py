# -*- coding: utf-8 -*-
# Copyright (c) 2016, French National Center for Scientific Research (CNRS)
# Distributed under the (new) BSD License. See LICENSE for more info.

import numpy as np

from ..core import Node, register_node_type
from pyqtgraph.Qt import QtCore, QtGui
from pyqtgraph.util.mutex import Mutex

import struct
import time

try:
    import serial
    HAVE_PYSERIAL = True
except ImportError:
    HAVE_PYSERIAL = False

_START_BYTE = 0xA0  # start of data packet
_END_BYTE = 0xC0  # end of data packe

# _START_BYTE = b'\xA0'
# _END_BYTE = b'\xC0'

class OpenBCIThread(QtCore.QThread):
    def __init__(self, outputs, serial_port, nb_channel, nb_aux):
        QtCore.QThread.__init__(self)
        self.outputs = outputs
        self.n = 0
        self.serial_port = serial_port
        self.packet_bsize = 3 +(nb_channel*3)+(nb_aux*2)
        # self.data = np.zeros( self.packet_bsize, dtype=np.uint8)
        self.chan_values = np.zeros(nb_channel, dtype=np.int64)
        self.aux_values = np.zeros(nb_aux, dtype=np.int64)
        self.count_lost_bytes = 0
        self.nb_channel = nb_channel
        self.nb_aux = nb_aux

        self.lock = Mutex()
        self.running = False
        
    def run(self):
        with self.lock:
            self.running = True
        
        self.serial_port.write('b'.encode('utf-8')) # command board to start streaming
        while True:
            with self.lock:
                    if not self.running:
                        break
            
            message = self.serial_port.read()
            unpacked = struct.unpack('B', message)[0]

            if unpacked == _START_BYTE:
                if self.count_lost_bytes!=0:
                    print("Lost %i bytes before reading the begining of a packet"%self.count_lost_bytes)
                    self.count_lost_bytes=0
                # self.data[0] = unpacked
                data = self.serial_port.read(self.packet_bsize-2)
                last_byte = struct.unpack('B', self.serial_port.read())[0]
                if last_byte == _END_BYTE:
                    self.decode(data)
                else:
                    print("Wrong packet")
                    self.chan_values[:] = 0
                    self.aux_values[:] = 0 
                self.n += 1 
                self.outputs['chan'].send(self.n, self.chan_values)
                self.outputs['aux'].send(self.n, self.aux_values)
            else:
                self.count_lost_bytes+=1

    def decode(self, data):
        """
        Parses incoming data packet into node outputs.
        Incoming Packet Structure:
        Sample ID(1)|Channel Data(24)|Aux Data(6)
        0-255|8, 3-byte signed ints|3 2-byte signed ints
        """
        jj=1 # First byte is Sample ID..
        for ii in range(self.nb_channel):
            data_chan = data[jj:jj+3]
            unpacked = struct.unpack('3B', data_chan)
            #3byte int in 2s compliment
            if (unpacked[0] >= 127):
                pre_fix = b'\xFF'
            else:
                pre_fix = b'\x00'
            data_chan = pre_fix + data_chan
            self.chan_values[ii] = struct.unpack('>i', data_chan)[0]
            jj=jj+3

        jj=25 
        for ii in range(self.nb_aux):
            acc = struct.unpack('>h', data[jj:jj+2])[0]
            self.aux_values[ii]=acc
            jj=jj+2


    def stop(self):
        self.serial_port.write('s'.encode('utf-8'))
        with self.lock:
            self.running = False


class OpenBCI(Node):
    """
    This class is a bridge between Pyacq and the 32bit board OpenBCI
    amplifier from the open source project http://openbci.com.
    Daisy board version for now 
    """
    _output_specs = {'chan' : dict(streamtype='analogsignal',dtype='int64',
                            shape=(-1, 8), sample_rate=250., timeaxis=0, nb_channel = 8),
                    'aux'   : dict(streamtype='analogsignal', dtype='int64',
                            shape=(-1, 3), sample_rate=128., time_axis=0, nb_channel = 3)
                    }


    def __init__(self, **kargs):
        Node.__init__(self, **kargs)
        assert HAVE_PYSERIAL, "OpenBCI node depends on the `pyserial` package, but it could not be imported."

    def _configure(self, board_name="Daisy", device_handle='/dev/ttyUSB0', device_baud=115200,
                    nb_channel=8, nb_aux=3, sample_rate=250., packet_bsize=33):  #"Daisy" board params
        """
        Parameters
        ----------
        board_name : str
            Name of the board used
        device_handle : str
            Path to the device. Linux   : '/dev/ttyUSB0'
                                Mac     : '/dev/tty.usbserial-DN0096XA'
                                Windows : 'COM3'
        device_baud : int
            baud of the serial connection
        nb_channel : int
            Board number of channels 
        nb_aux : int
            Board number of aux signals
        sample_rate : int
            Board sample rate
        packet_bsize : int
            Number of bytes of data packet
        """
        self.board_name = board_name
        self.device_handle = device_handle
        self.device_baud = device_baud
        self.packet_bsize = packet_bsize
        self.nb_channel = nb_channel
        self.nb_aux = nb_aux
    
        self.outputs['chan'].spec['shape'] = (-1, nb_channel)
        self.outputs['chan'].spec['sample_rate'] = sample_rate
        self.outputs['chan'].spec['nb_channel'] = nb_channel

    def _initialize(self):
        self.serial_port = serial.Serial(port=self.device_handle, baudrate=self.device_baud)
        self.reset()
        self.print_incoming()
        self._thread = OpenBCIThread(self.outputs, self.serial_port, self.nb_channel, self.nb_aux)

    def _start(self):
        self._thread.start()

    def _stop(self):
        print("stop thread")
        self._thread.stop()
        self._thread.wait()
    
    def _close(self):
        self.serial_port.close()
        pass
    
    def reset(self):
        self.serial_port.write('v'.encode('utf-8'))
        #wait for device to be ready
        time.sleep(2)

    def print_incoming(self):
        if self.serial_port.inWaiting():
            message = ''
            #Look for end sequence $$$
            while '$$$' not in message:
                message += self.serial_port.read().decode("utf-8")
            print(message)
        else:
            print("No Message")

    def print_register_settings(self):
        self.serial_port.write('?'.encode('utf-8'))
        time.sleep(0.5)
        self.print_incoming()

    # def set_channel(self, channel, toggle_position):
    #     #Commands switch channel ON or OFF (1/0)
    #     if toggle_position == 1:
    #         if self.board_name == 'Daisy':
    #             code = ['!', '@', '#', '$', '%', '^', '&', '*']
    #         else:
    #             code = ['!', '@', '#', '$', '%', '^', '&', '*', 'Q', 'W', 'E', 'R', 'T', 'Y', 'U', 'I']
        
    #     if toggle_position == 0:
    #         if self.board_name == 'Daisy':
    #             code = ['1', '2', '3', '4', '5', '6', '7', '8']
    #         else:
    #             code = ['1', '2', '3', '4', '5', '6', '7', '8', 'q', 'w', 'e', 'r', 't', 'y', 'u', 'i']

    #     self.serial_port.write(code[channel].encode('utf-8'))

    
register_node_type(OpenBCI)
