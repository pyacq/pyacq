# -*- coding: utf-8 -*-
"""

Emotiv acquisition :
Reverse engineering and original crack code written by

    Cody Brocious (http://github.com/daeken)
    Kyle Machulis (http://github.com/qdot)

Many thanks for their contribution.


Need python-crypto.

"""
import multiprocessing as mp
import numpy as np
import msgpack
import time
from collections import OrderedDict

from .base import DeviceBase

import platform
WINDOWS = (platform.system() == "Windows")

try:
    import pywinusb.hid as hid
except:
    pass

import os
from subprocess import check_output
from Crypto.Cipher import AES
from Crypto import Random

import Queue
tasks = Queue.Queue()

_channel_names = ['F3', 'F4', 'P7', 'FC6', 'F7', 'F8',
                  'T7', 'P8', 'FC5', 'AF4', 'T8', 'O2', 'O1', 'AF3']

sensorBits = {
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
quality_bits = [99, 100, 101, 102, 103, 104,
                105, 106, 107, 108, 109, 110, 111, 112]


def create_analog_subdevice_param(channel_names):
    n = len(channel_names)
    d = {
        'type': 'AnalogInput',
        'nb_channel': n,
                'params': {},
                'by_channel_params': {
                    'channel_indexes': range(n),
                    'channel_names': channel_names,
                }
    }
    return d


def get_info(device):
    info = {}
    info['class'] = 'EmotivMultiSignals'
    if WINDOWS:
        # EMOTIV
        info['device_path'] = device.device_path
        info['board_name'] = '{} #{}'.format(
            device.vendor_name, device.serial_number).replace('\n', '').replace('\r', '')
        info['serial'] = device.serial_number
        info['hid'] = device

    else:
        info['device_path'] = device
        name = info['device_path'].strip('/dev/')
        realInputPath = os.path.realpath("/sys/class/hidraw/" + name)
        path = '/'.join(realInputPath.split('/')[:-4])
        with open(path + "/manufacturer", 'r') as f:
            manufacturer = f.readline()
        with open(path + "/serial", 'r') as f:
            serial = f.readline().strip()

        info['board_name'] = '{} #{}'.format(
            manufacturer, serial).replace('\n', '').replace('\r', '')
        info['serial'] = serial

    # PYACQ
    info['global_params'] = {'buffer_length': 60., }
    info['subdevices'] = []
    info['subdevices'].append(create_analog_subdevice_param(_channel_names))
    quality_name = ['Quality {}'.format(n) for n in _channel_names]
    info['subdevices'].append(create_analog_subdevice_param(quality_name))
    info['subdevices'].append(create_analog_subdevice_param(['X', 'Y']))

    return info


def dump(obj):
    for attr in dir(obj):
        print "obj.%s = %s" % (attr, getattr(obj, attr))


class EmotivMultiSignals(DeviceBase):

    def __init__(self,  **kargs):
        DeviceBase.__init__(self, **kargs)

    @classmethod
    def get_available_devices(cls):
        devices = OrderedDict()

        if WINDOWS:
            try:
                for device in hid.find_all_hid_devices():
                    if device.product_name == 'Emotiv RAW DATA':
                        devices[
                            'Emotiv '+device.serial_number] = get_info(device)
            finally:
                pass

        else:
            serials = {}
            for name in os.listdir("/sys/class/hidraw"):
                realInputPath = os.path.realpath("/sys/class/hidraw/" + name)
                path = '/'.join(realInputPath.split('/')[:-4])
                try:
                    with open(path + "/manufacturer", 'r') as f:
                        manufacturer = f.readline()
                    if "emotiv" in manufacturer.lower():
                        with open(path + "/serial", 'r') as f:
                            serial = f.readline().strip()
                            if serial not in serials:
                                serials[serial] = []
                            serials[serial].append(name)
                except IOError as e:
                    print "Couldn't open file: %s" % e

            for serial, names in serials.items():
                device_path = '/dev/'+names[1]
                info = get_info(device_path)
                devices['Emotiv '+device_path] = info

        return devices

    def configure(self, buffer_length=60,
                  subdevices=None,
                  ):
        self.params = {'buffer_length': buffer_length,
                       'subdevices': subdevices,
                       }
        self.__dict__.update(self.params)
        self.configured = True

    def initialize(self):

        devices = EmotivMultiSignals.get_available_devices()
        self.device = devices.values()[0]

        if self.subdevices is None:
            self.subdevices = self.device['subdevices']

        self.sampling_rate = 128.
        self.packet_size = 1
        l = int(self.sampling_rate*self.buffer_length)
        self.buffer_length = (l - l % self.packet_size)/self.sampling_rate

        self.name = '{}'.format(self.device['board_name'])

        self.streams = []
        for s, sub in enumerate(self.subdevices):
            stream = self.streamhandler.new_AnalogSignalSharedMemStream(
                name=self.name+str(s), sampling_rate=self.sampling_rate,
                nb_channel=sub['nb_channel'], buffer_length=self.buffer_length,
                packet_size=self.packet_size, dtype=np.float64,
                channel_names=sub['by_channel_params']['channel_names'],
                channel_indexes=sub['by_channel_params']['channel_indexes'],
            )
            self.streams.append(stream)

    def start(self):

        self.stop_flag = mp.Value('i', 0)  # flag pultiproc  = global
        self.process = mp.Process(target=emotiv_mainLoop,
                                  args=(self.stop_flag, self.streams, self.device))
        self.process.start()

        print 'FakeMultiAnalogChannel started:', self.name
        self.running = True

    def stop(self):
        self.stop_flag.value = 1
        self.process.join()

        print 'FakeMultiAnalogChannel stopped:', self.name
        self.running = False

    def close(self):
        pass


def setupCrypto(serial):
    type = 0  # feature[5]
    type &= 0xF
    type = 0
    # I believe type == True is for the Dev headset, I'm not using that.
    # That's the point of this library in the first place I thought.
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
    # It doesn't make sense to have more than one greenlet handling this
    # as data needs to be in order anyhow. I guess you could assign an ID or something
    # to each packet but that seems like a waste also or is it? The ID might
    # be useful if your using multiple headsets or usb sticks.
    key = ''.join(k)
    iv = Random.new().read(AES.block_size)
    cipher = AES.new(key, AES.MODE_ECB, iv)
    return cipher


def get_level(data, bits):
    level = 0
    for i in range(13, -1, -1):
        level <<= 1
        b, o = (bits[i] / 8) + 1, bits[i] % 8
        level |= (ord(data[b]) >> o) & 1
    return level


def emotiv_mainLoop(stop_flag, streams, device):
    import zmq
    abs_pos = pos = 0

    # setup cryto
    cipher = setupCrypto(device['serial'])

    streamChan, streamImp, streamGyro = streams

    # Data channels socket
    context = zmq.Context()
    socket_chan = context.socket(zmq.PUB)
    socket_chan.bind("tcp://*:{}".format(streamChan['port']))

    # Impedance channels socket
    socket_imp = context.socket(zmq.PUB)
    socket_imp.bind("tcp://*:{}".format(streamImp['port']))

    # Gyro channels socket
    socket_gyro = context.socket(zmq.PUB)
    socket_gyro.bind("tcp://*:{}".format(streamGyro['port']))

    packet_size = streamChan['packet_size']
    sampling_rate = streamChan['sampling_rate']

    np_arr_chan = streamChan['shared_array'].to_numpy_array()
    np_arr_imp = streamImp['shared_array'].to_numpy_array()
    np_arr_gyro = streamGyro['shared_array'].to_numpy_array()

    half_size = np_arr_chan.shape[1]/2    # same for the others

    impedance_qualities = {}
    for name in _channel_names + ['X', 'Y', 'Unknown']:
        impedance_qualities[name] = 0.

    if WINDOWS:
        device['hid'].open()
        device['hid'].set_raw_data_handler(emotiv_handler)
    else:
        hidraw = open(device['device_path'])

    while True:
        # READ DATA
        if WINDOWS:
            crypted_data = tasks.get(True)
        else:
            crypted_data = hidraw.read(32)

        # PROCESS
        data = cipher.decrypt(
            crypted_data[:16]) + cipher.decrypt(crypted_data[16:])

        # current impedance quality
        sensor_num = ord(data[0])
        num_to_name = {0: 'F3',  1: 'FC5', 2: 'AF3',  3: 'F7', 4: 'T7', 5: 'P7',
                       6: 'O1', 7: 'O2', 8: 'P8', 9: 'T8', 10: 'F8', 11: 'AF4',
                       12: 'FC6', 13: 'F4', 14: 'F8', 15: 'AF4',
                       64: 'F3', 65: 'FC5', 66: 'AF3', 67: 'F7', 68: 'T7', 69: 'P7',
                       70: 'O1', 71: 'O2', 72: 'P8', 73: 'T8', 74: 'F8', 75: 'AF4',
                       76: 'FC6', 77: 'F4', 78: 'F8', 79: 'AF4',
                       80: 'FC6',
                       }
        if sensor_num in num_to_name:
            sensor_name = num_to_name[sensor_num]
            impedance_qualities[sensor_name] = get_level(
                data, quality_bits) / 540

        for c, channel_name in enumerate(_channel_names):
            bits = sensorBits[channel_name]
            # channel value
            value = get_level(data, bits)
            np_arr_chan[c, pos] = value
            np_arr_chan[c, pos+half_size] = value

            # channel qualities
            np_arr_imp[c, pos] = impedance_qualities[channel_name]
            np_arr_imp[c, pos+half_size] = impedance_qualities[channel_name]

        gyroX = ord(data[29]) - 106
        gyroY = ord(data[30]) - 105
        np_arr_gyro[:, pos] = [gyroX, gyroY]
        np_arr_gyro[:, pos+half_size] = [gyroX, gyroY]

        abs_pos += packet_size
        pos = abs_pos % half_size

        socket_chan.send(msgpack.dumps(abs_pos))
        socket_imp.send(msgpack.dumps(abs_pos))
        socket_gyro.send(msgpack.dumps(abs_pos))

        if stop_flag.value:
            print 'will stop'
            break


# Windows handler
def emotiv_handler(data):
    """
    Receives packets from headset for Windows. Sends them to the crypto process
    """
    assert data[0] == 0
    tasks.put_nowait(''.join(map(chr, data[1:])))
    return True


Emotiv = EmotivMultiSignals
