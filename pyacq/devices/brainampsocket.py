import numpy as np

from ..core import Node, register_node_type
from pyqtgraph.Qt import QtCore, QtGui
from pyqtgraph.util.mutex import Mutex

import socket
import struct


_dtype_trigger = [('pos', 'int64'),
                ('points', 'int64'),
                ('channel', 'int64'),
                ('type', 'S16'),  # TODO check size
                ('description', 'S16'),  # TODO check size
                ]


def recv_brainamp_frame(brainamp_socket, reqsize):
    buf =b''
    n = 0
    while len(buf) < reqsize:
        newbytes = brainamp_socket.recv(reqsize - n)
        if newbytes == '':
            raise RuntimeError('connection broken')
        buf = buf+newbytes
        n += len(buf)
    
    if len(buf)>=reqsize:
        buf = buf[:reqsize]
    return buf


class BrainAmpThread(QtCore.QThread):
    def __init__(self, outputs, brainamp_host, brainamp_port, nb_channel, parent=None):
        QtCore.QThread.__init__(self)
        self.outputs = outputs
        self.brainamp_host= brainamp_host
        self.brainamp_port= brainamp_port
        self.nb_channel = nb_channel

        self.lock = Mutex()
        self.running = False
        
    def run(self):
        brainamp_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        brainamp_socket.connect((self.brainamp_host, self.brainamp_port))
        with self.lock:
            self.running = True
        
        dt = np.dtype('float32')
        
        head = 0
        head_marker = 0
        while True:
            with self.lock:
                    if not self.running:
                        break
            
            buf_header = recv_brainamp_frame(brainamp_socket, 24)
            (id1, id2, id3, id4, msgsize, msgtype) = struct.unpack('<llllLL', buf_header)
            
            rawdata = recv_brainamp_frame(brainamp_socket, msgsize - 24)
            # TODO  msgtype == 3 (msgtype == 1 is header done in Node.configure)
            if msgtype == 4:
                #~ block, chunk, markers = get_signal_and_markers(rawdata, self.nb_channel)
                hs = 12
                
                # Extract numerical data
                block, points, nb_marker = struct.unpack('<LLL', rawdata[:hs])
                sigsize = dt.itemsize * points * self.nb_channel
                sigs = np.frombuffer(rawdata[hs:hs+sigsize], dtype=dt)
                sigs = sigs.reshape(points, self.nb_channel)
                head += points
                self.outputs['signals'].send(head, sigs)

                # Extract markers
                markers = np.empty((nb_marker,), dtype=_dtype_trigger)
                index = hs + sigsize
                for m in range(nb_marker):
                    markersize, = struct.unpack('<L', rawdata[index:index+4])
                    markers['pos'][m], markers['points'][m],markers['channel'][m] = struct.unpack('<LLl', rawdata[index+4:index+16])
                    markers['type'][m], markers['description'][m] = rawdata[index+16:index+markersize].tostring().split('\x00')[:2]
                    index = index + markersize
                head_marker += nb_marker
                self.outputs['triggers'].send(nb_marker, markers)
        
        brainamp_socket.close()
    
    def stop(self):
        with self.lock:
            self.running = False


class BrainAmpSocket(Node):
    """
    BrainAmp EEG amplifier from Brain Products http://www.brainproducts.com/.
    
    This class is a bridge between pyacq and the socket-based data streaming
    provided by the Vision recorder acquisition software.
    """
    _output_specs = {'signals': dict(streamtype='analogsignal',dtype='float32',
                                                shape=(-1, 32), compression ='', timeaxis=0,
                                                sample_rate = 512.),
                                'triggers': dict(streamtype = 'event', dtype = _dtype_trigger,
                                                shape = (-1,)),
                                }

    def __init__(self, **kargs):
        Node.__init__(self, **kargs)

    def _configure(self, brainamp_host='localhost', brainamp_port=51244):
        '''
        Parameters
        ----------
        brainamp_host : str
            adress used by Vision recorder to send data. Default is 'localhost'.
        brainamp_port : int
            port used by Brain Vision recorder. Default is 51244.
        '''
        self.brainamp_host = brainamp_host
        self.brainamp_port = brainamp_port
        
        # recv header from brain amp
        brainamp_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        brainamp_socket.connect((self.brainamp_host, self.brainamp_port))
        buf_header = recv_brainamp_frame(brainamp_socket, 24)
        id1, id2, id3, id4, msgsize, msgtype = struct.unpack('<llllLL', buf_header)
        rawdata = recv_brainamp_frame(brainamp_socket, msgsize - 24)
        assert msgtype == 1, 'First message from brainamp is not type 1'
        self.nb_channel, sample_interval = struct.unpack('<Ld', rawdata[:12])
        n = self.nb_channel
        sample_interval = sample_interval*1e-6
        self.sample_rate = 1./sample_interval
        self.resolutions = np.array(struct.unpack('<'+'d'*n, rawdata[12:12+8*n]), dtype='f')
        self.channel_names = rawdata[12+8*n:].decode().split('\x00')[:-1]
        #~ self.channel_indexes = range(nb_channel)
        brainamp_socket.close()
        
        self.outputs['signals'].spec['shape'] = (-1, self.nb_channel)
        self.outputs['signals'].spec['sample_rate'] = self.sample_rate
        self.outputs['signals'].spec['nb_channel'] = nb_channel

    def _initialize(self):
        self._thread = BrainAmpThread(self.outputs, self.brainamp_host, self.brainamp_port,
                             self.nb_channel, parent=self)

    def _start(self):
        self._thread.start()

    def _stop(self):
        self._thread.stop()
        self._thread.wait()
    
    def _close(self):
        pass
    

register_node_type(BrainAmpSocket)
