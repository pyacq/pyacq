from ..core import Node, register_node_type
from pyqtgraph.Qt import QtCore, QtGui
from pyqtgraph.util.mutex import Mutex
import os
import numpy as np

try:
    from Crypto.Cipher import AES
    from Crypto import Random
    HAVE_PYCRYPTO = True
except ImportError:
    HAVE_PYCRYPTO = False

import platform
WINDOWS = (platform.system() == "Windows")
if WINDOWS: 
    try:
        import pywinusb.hid as hid
        HAVE_PYWINUSB = True
    except ImportError:
        HAVE_PYWINUSB = False

_channel_names = ['F3', 'F4', 'P7', 'FC6', 'F7', 'F8',
                  'T7', 'P8', 'FC5', 'AF4', 'T8', 'O2', 'O1', 'AF3']

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
_quality_bits = [
    99, 100, 101, 102, 103, 104, 105, 106, 107, 108, 109, 110, 111, 112]
_quality_num_to_name = {0: 'F3', 1: 'FC5', 2: 'AF3', 3: 'F7', 4: 'T7',
                        5: 'P7', 6: 'O1', 7: 'O2', 8: 'P8', 9: 'T8',
                        10: 'F8', 11: 'AF4', 12: 'FC6', 13: 'F4', 14: 'F8',
                        15: 'AF4', 64: 'F3', 65: 'FC5', 66: 'AF3', 67: 'F7',
                        68: 'T7', 69: 'P7', 70: 'O1', 71: 'O2', 72: 'P8',
                        73: 'T8', 74: 'F8', 75: 'AF4', 76: 'FC6', 77: 'F4',
                        78: 'F8', 79: 'AF4', 80: 'FC6'}


def setupCrypto(serial):
    # original code fom http://github.com/qdot
    #type = 0
    #type &= 0xF
    #type = 0
    #k = [ serial[-1], '\0', serial[-2]]
    # if type:
    #    k += [ 'H', serial[-1], '\0', serial[-2], 'T', serial[-3], '\x10', serial[-4], 'B']
    # else:
    #    k += ['T', serial[-3], '\x10', serial[-4], 'B', serial[-1], '\0', serial[-2], 'H']
    #k += [serial[-3], '\0', serial[-4], 'P']
    k = [serial[-1], '\0', serial[-2], 'T', serial[-3], '\x10', serial[-4],
         'B', serial[-1], '\0', serial[-2], 'H', serial[-3], '\0', serial[-4],
         'P']
    key = ''.join(k)
    iv = Random.new().read(AES.block_size)
    cipher = AES.new(key, AES.MODE_ECB, iv)
    return cipher

def get_level(data, bits):
    level = 0
    for i in range(13, -1, -1):
        level <<= 1
        b, o = (bits[i] // 8) + 1, bits[i] % 8
        level |= (data[b] >> o) & 1
    return level


class Unix_EmotivThread(QtCore.QThread):

    def __init__(self, dev_handle, parent=None):
        QtCore.QThread.__init__(self, parent)
        self.lock = Mutex()
        self.running = False
        self.dev_handle = dev_handle

    def run(self):
        with self.lock:
            self.running = True
        while True:
            with self.lock:
                if not self.running:
                    break

            crypted_buffer = self.dev_handle.read(32)        
            self.parent().process_data(crypted_buffer)
        
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
    device :
        - For Linux, it's the path to the usb hidraw used
        - For Windows, it's the hid object associated with the USB key
    """
    _output_specs = {'signals': dict(streamtype='analogsignal', dtype='int64',
                                     shape=(-1, 14), sample_rate=128., timeaxis=0),
                     'impedances': dict(streamtype='analogsignal', dtype='float64',
                                        shape=(-1, 14), sample_rate=128., time_axis=0),
                     'gyro': dict(streamtype='analogsignal', dtype='int64',
                                  shape=(-1, 2), sample_rate=128., time_axis=0)
                     }  # TODO Why we don't keep channel names ??

    def __init__(self, **kargs):
        Node.__init__(self, **kargs)
        assert HAVE_PYCRYPTO, "Emotiv node depends on the `pycrypto` package, but it could not be imported."
        if WINDOWS:
            assert HAVE_PYWINUSB, "Emotiv node on Windows depends on the `pywinusb` package, but it could not be imported."
            
        self.device_info = dict()

    def _configure(self, device_handle='/dev/hidraw0'):
        
        self.device_path = device_handle
        
        if WINDOWS:
            self.dev_handle = hid.core.HidDevice(device_handle)
            self.serial = self.dev_handle.serial_number
        else:
            self.name = self.device_path.strip('/dev/')
            real_input_path = os.path.realpath("/sys/class/hidraw/" + self.name)
            path = '/'.join(real_input_path.split('/')[:-4])
            with open(path + "/manufacturer", 'r') as f:
                self.manufacturer = f.readline()
            with open(path + "/serial", 'r') as f:
                self.serial = f.readline().strip()

    def _initialize(self):
        self.values = np.zeros(len(_channel_names), dtype=np.int64)
        self.imp = np.zeros(len(_channel_names), dtype=np.float64)
        self.gyro = np.zeros(2, dtype=np.int64)
        self.n = 0
        self.cipher = setupCrypto(self.serial)
        if not WINDOWS:
            self.dev_handle = open(self.device_path, mode='rb')

    def _start(self):
        if WINDOWS:
            self.dev_handle.open()
            self.dev_handle.set_raw_data_handler(self.win_emotiv_process)
        else:
            self._thread = Unix_EmotivThread(self.dev_handle, parent=self)
            self._thread.start()

    def _stop(self):
        if WINDOWS:
            self.dev_handle.set_raw_data_handler(None)
        else:
            self._thread.stop()
            self._thread.wait()

    def _close(self):
        self.dev_handle.close()
        
    def process_data(self, crypted_buffer):
        data = self.cipher.decrypt(crypted_buffer[:16]) + self.cipher.decrypt(crypted_buffer[16:])
        
        # impedance value
        sensor_num = data[0]
        if sensor_num in _quality_num_to_name:
            sensor_name = _quality_num_to_name[sensor_num]
            if sensor_name in _channel_names:
                channel_index = _channel_names.index(sensor_name)
                self.imp[channel_index] = get_level(data, _quality_bits) / 540
        # channel signals value
        for c, channel_name in enumerate(_channel_names):
            bits = _sensorBits[channel_name]
            self.values[c] = get_level(data, bits)
        # gyro value
        self.gyro[0] = data[29] - 106  # X
        self.gyro[1] = data[30] - 105  # Y
        
        self.n += 1
        self.outputs['signals'].send(self.n, self.values)
        self.outputs['impedances'].send(self.n, self.imp)
        self.outputs['gyro'].send(self.n, self.gyro)

    def win_emotiv_process(self, data):
        #assert data[0] == 0
        crypted_buffer = bytes(data[1:])
        self.process_data(crypted_buffer)
        

register_node_type(Emotiv)
