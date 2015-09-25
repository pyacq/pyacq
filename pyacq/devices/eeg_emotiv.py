

from ..core import Node, register_node_type
from pyqtgraph.Qt import QtCore, QtGui
from pyqtgraph.util.mutex import Mutex

import numpy as np
import msgpack
import time

try:
    from Crypto.Cipher import AES
    from Crypto import Random
    HAVE_PYCRYPTO = True
except ImportError:
    HAVE_PYCRYPTO = False


_channel_names = [ 'F3', 'F4', 'P7', 'FC6', 'F7', 'F8','T7','P8','FC5','AF4','T8','O2','O1','AF3']

_sensorBits = {
  'F3': [10, 11, 12, 13, 14, 15, 0, 1, 2, 3, 4, 5, 6, 7],
  'FC5': [28, 29, 30, 31, 16, 17, 18, 19, 20, 21, 22, 23, 8, 9],
  'AF3': [46, 47, 32, 33, 34, 35, 36, 37, 38, 39, 24, 25, 26, 27],
  'F7': [48, 49, 50, 51, 52, 53, 54, 55, 40, 41, 42, 43, 44, 45],
  'T7': [66, 67, 68, 69, 70, 71, 56, 57, 58, 59, 60, 61, 62, 63],
  'P7': [84, 85, 86, 87, 72, 73, 74, 75, 76, 77, 78, 79, 64, 65],
  'O1': [102, 103, 88, 89, 90, 91, 92, 93, 94, 95, 80, 81, 82, 83],
  'O2': [140, 141, 142, 143, 128, 129, 130, 131, 132, 133, 134, 135, 120, 121],
  'P8': [158, 159, 144, 145, 146, 147, 148, 149, 150, 151, 136, 137, 138, 139],
  'T8': [160, 161, 162, 163, 164, 165, 166, 167, 152, 153, 154, 155, 156, 157],
  'F8': [178, 179, 180, 181, 182, 183, 168, 169, 170, 171, 172, 173, 174, 175],
  'AF4': [196, 197, 198, 199, 184, 185, 186, 187, 188, 189, 190, 191, 176, 177],
  'FC6': [214, 215, 200, 201, 202, 203, 204, 205, 206, 207, 192, 193, 194, 195],
  'F4': [216, 217, 218, 219, 220, 221, 222, 223, 208, 209, 210, 211, 212, 213]
}
_quality_bits = [99, 100, 101, 102, 103, 104, 105, 106, 107, 108, 109, 110, 111, 112]


def setupCrypto(serial):
    type = 0 #feature[5]
    type &= 0xF
    type = 0
    k = ['\0'] * 16
    k[0] = serial[-1]
    k[1] = '\0'
    k[2] = serial[-2]
    if type:
        k[3] = 'H'
        k[4] = serial[-1]
        k[5] = '\0'
        k[6] = serial[-2]
        k[7] = 'T'
        k[8] = serial[-3]
        k[9] = '\x10'
        k[10] = serial[-4]
        k[11] = 'B'
    else:
        k[3] = 'T'
        k[4] = serial[-3]
        k[5] = '\x10'
        k[6] = serial[-4]
        k[7] = 'B'
        k[8] = serial[-1]
        k[9] = '\0'
        k[10] = serial[-2]
        k[11] = 'H'
    k[12] = serial[-3]
    k[13] = '\0'
    k[14] = serial[-4]
    k[15] = 'P'
    key = ''.join(k)
    iv = Random.new().read(AES.block_size)
    cipher = AES.new(key, AES.MODE_ECB, iv)
    return cipher


def get_level(data, bits):
    level = 0
    for i in range(13, -1, -1):
        level <<= 1
        b, o = (bits[i] / 8) + 1, bits[i] % 8
        #~ level |= (ord(data[b]) >> o) & 1                    #Why b is a float that makes ord hungry ?
        b = int(b)                                                         
        level |= (data[b] >> o) & 1
    return level


class EmotivIOThread(QtCore.QThread):
    def __init__(self, hidraw_file, cipher, outputs, parent = None):
        QtCore.QThread.__init__(self)
        self.outputs= outputs
        self.hidraw_file = hidraw_file
        self.cipher = cipher
        
        self.values = np.zeros((1, len(_channel_names)), dtype = np.int64 ) 
        self.imp = np.zeros((1, len(_channel_names)), dtype = np.float64 )
        self.gyro = np.zeros((1, 2), dtype = np.int64)
        
        self.impedance_qualities = { }
        for name in _channel_names + ['X', 'Y', 'Unknown']:
            self.impedance_qualities[name] = 0.
        
        self.num_to_name = { 0 : 'F3',  1:'FC5', 2 : 'AF3',  3 : 'F7', 4:'T7', 5 : 'P7', 
                                                6 : 'O1', 7 : 'O2', 8: 'P8', 9 : 'T8', 10: 'F8', 11 : 'AF4', 
                                                12 : 'FC6', 13: 'F4', 14 : 'F8', 15:'AF4', 
                                                64 : 'F3', 65 : 'FC5', 66 : 'AF3', 67 : 'F7', 68 : 'T7', 69 : 'P7', 
                                                70 : 'O1', 71 : 'O2', 72: 'P8', 73 : 'T8', 74: 'F8', 75 : 'AF4', 
                                                76 : 'FC6', 77: 'F4', 78 : 'F8', 79:'AF4', 
                                                80 : 'FC6'}
        
        self.lock = Mutex()
        self.running = False
        
    def run(self):
        with self.lock:
            self.running = True
        n = 0
        
        while True:  
            with self.lock:
                if not self.running:
                    break
            crypted_dataBuffer = bytearray(self.hidraw_file.read(32))         
            data = self.cipher.decrypt(bytes(crypted_dataBuffer[:16])) +self.cipher.decrypt(bytes(crypted_dataBuffer[16:]))
            
            #~ sensor_num = ord(data[0])
            sensor_num = data[0]
            
            if sensor_num in self.num_to_name:
                sensor_name = self.num_to_name[sensor_num]
                self.impedance_qualities[sensor_name] = get_level(data, _quality_bits) / 540
            
            for c, channel_name in enumerate(_channel_names):
                bits = _sensorBits[channel_name]
                # channel value
                self.values[0,c] = get_level(data, bits)
                self.imp[0,c] = self.impedance_qualities[channel_name]
            
            #~ self.gyro[0] = ord(data[29]) - 106 #X        #Why b is a float that makes ord hungry ?
            #~ self.gyro[1] = ord(data[30]) - 105 #Y
            self.gyro[0,0] = data[29]- 106 #X
            self.gyro[0,1] = data[30] - 105 #Y
            
            n += 1
            self.outputs['signals'].send(n, self.values)
            self.outputs['impedances'].send(n, self.imp)
            self.outputs['gyro'].send(n,self.gyro)
            
            # Maybe not needed if hidraw handle it ?
            time.sleep(1./self.outputs['signals'].params['sampling_rate'])


    def stop(self):
        with self.lock:
            self.running = False



class Emotiv(Node):
    """
    Simple eeg emotiv device to access eeg, impedances and gyro data in a Node.
    
    Reverse engineering and original crack code written by
    Cody Brocious (http://github.com/daeken)
    Kyle Machulis (http://github.com/qdot)
    Many thanks for their contribution.
    
    Emotiv USB emit 32-bytes reports at a rate of 128Hz, encrypted via AES
    see https://github.com/qdot/emokit/blob/master/doc/emotiv_protocol.asciidoc
    for more details
    
    Parameters for configure():
    ----
    device_info :  dict containing :
        - Path to the usb hidraw used
        - Serial number of USB key
    """ 
    
    _output_specs = { 'signals'    : dict(streamtype = 'analogsignal',dtype = 'int64', 
                                                        shape = (-1,14), sampling_rate = 128.,  timeaxis=0), 
                                'impedances' : dict(streamtype = 'analogsignal',dtype = 'float64',
                                                        shape = (-1,14), sampling_rate = 128.,  time_axis=0),
                                'gyro'           : dict(streamtype = 'analogsignal',dtype = 'int64',
                                                        shape = (-1,2), sampling_rate = 128.,  time_axis=0)
                                }  # TODO Why we don't keep channel names ??
        
    def __init__(self, **kargs):
        Node.__init__(self, **kargs)
        assert HAVE_PYCRYPTO, "Emotiv node depends on the `pycrypto` package, but it could not be imported."
        self.device_info = dict()
            
    def _configure(self, device_info = []):
        self.device_info['path'] = device_info['path'] 
        self.device_info['serial'] = device_info['serial']
            
    def _initialize(self):
        self.cipher = setupCrypto(self.device_info['serial'])
        self.hidraw_file = open(self.device_info['path'],  mode = 'rb') # read as binary
            
    def _start(self):
        self._thread = EmotivIOThread(self.hidraw_file, self.cipher, self.outputs)
        self._thread.start()
            
    def _stop(self):
        self._thread.stop()
            
    def _close(self):
        close(self.device_path)
        del self._thread
            
            
            
register_node_type(Emotiv)