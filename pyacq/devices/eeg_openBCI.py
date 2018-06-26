# -*- coding: utf-8 -*-
# Copyright (c) 2016, French National Center for Scientific Research (CNRS)
# Distributed under the (new) BSD License. See LICENSE for more info.

import numpy as np

from ..core import Node, register_node_type
from pyqtgraph.Qt import QtCore, QtGui
from pyqtgraph.util.mutex import Mutex

import struct
import time

import logging
logger = logging.getLogger(__name__)

try:
    import serial
    HAVE_PYSERIAL = True
except ImportError:
    HAVE_PYSERIAL = False

_START_BYTE = 0xA0  # start of data packet
_END_BYTE = 0xC0  # end of data packet


class OpenBCIThread(QtCore.QThread):
    def __init__(self, outputs, serial_port, nb_channel, nb_aux):
        QtCore.QThread.__init__(self)
        self.outputs = outputs
        self.n = 0
        self.serial_port = serial_port
        self.packet_bsize = 3 +(nb_channel*3)+(nb_aux*2)
        self.chan_values = np.zeros((1, nb_channel), dtype=np.int64)
        self.aux_values = np.zeros((1, nb_aux), dtype=np.int64)
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
                    logger.debug("Lost %i bytes before reading the begining of a packet"%self.count_lost_bytes)
                    self.count_lost_bytes=0
                # self.data[0] = unpacked
                data = self.serial_port.read(self.packet_bsize-2)
                last_byte = struct.unpack('B', self.serial_port.read())[0]
                if last_byte == _END_BYTE:
                    self.decode(data)
                else:
                    logger.debug("Wrong packet")
                    self.chan_values[0,:] = 0
                    self.aux_values[0,:] = 0
                self.n += 1
                self.outputs['chan'].send(self.chan_values, index=self.n)
                self.outputs['aux'].send(self.aux_values, index=self.n)
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
            self.chan_values[0,ii] = struct.unpack('>i', data_chan)[0]
            jj=jj+3

        jj=25
        for ii in range(self.nb_aux):
            acc = struct.unpack('>h', data[jj:jj+2])[0]
            self.aux_values[0,ii]=acc
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

    #TODO : this is a very basic code to grab data from 8 channel Daisy OpenBCI board.
    # next version will improve dialog with the board and auto-initialisation


    """
    _output_specs = {'chan' : dict(streamtype='analogsignal',dtype='int64'),
                     'aux'   : dict(streamtype='analogsignal', dtype='int64')}


    def __init__(self, **kargs):
        Node.__init__(self, **kargs)
        assert HAVE_PYSERIAL, "OpenBCI node depends on the `pyserial` package, but it could not be imported."

    def _configure(self, device_handle='/dev/ttyUSB0'):
        """
        Parameters
        ----------
        device_handle : str
            Path to the device. Linux   : '/dev/ttyUSB0'
                                Mac     : '/dev/tty.usbserial-DN0096XA'
                                Windows : 'COM3'
        """
        #"Daisy" board params
        self.board_name = "Daisy"
        self.device_handle = device_handle
        self.device_baud = 115200
        self.packet_bsize = 33
        self.nb_channel = 8
        self.nb_aux = 3

        self.outputs['chan'].spec['shape'] = (-1, self.nb_channel)
        self.outputs['chan'].spec['sample_rate'] = 250.
        self.outputs['chan'].spec['nb_channel'] = self.nb_channel

        self.outputs['aux'].spec['shape'] = (-1, self.nb_aux)
        self.outputs['aux'].spec['sample_rate'] = 250
        self.outputs['aux'].spec['nb_channel'] = self.nb_aux

    def after_output_configure(self, outputname):
        if outputname == 'chan':
            channel_info = [ {'name': 'ch{}'.format(c)} for c in range(self.nb_channel) ]
        elif outputname == 'aux':
            channel_info = [ {'name': 'aux{}'.format(c)} for c in range(self.nb_aux) ]
        self.outputs[outputname].params['channel_info'] = channel_info

    def _initialize(self):
        self.serial_port = serial.Serial(port=self.device_handle, baudrate=self.device_baud)
        self.reset_port()
        self.check_response()
        self._thread = OpenBCIThread(self.outputs, self.serial_port, self.nb_channel, self.nb_aux)

    def _start(self):
        self._thread.start()

    def _stop(self):
        self._thread.stop()
        self._thread.wait()

    def _close(self):
        self.serial_port.close()
        pass

    def reset_port(self):
        self.serial_port.write('v'.encode('utf-8'))
        #wait for device to be ready
        time.sleep(2)

    def check_response(self):
        if self.serial_port.inWaiting():
            message = ''
            #Look for end sequence $$$
            while '$$$' not in message:
                message += self.serial_port.read().decode("utf-8")
            logger.debug("recv message %s", message)
        else:
            logger.debug("no message recv")

    # def print_register_settings(self):
    #     self.serial_port.write('?'.encode('utf-8'))
    #     time.sleep(0.5)
    #     self.check_response()

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
