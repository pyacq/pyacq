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
 
try:
    import pywinusb.hid as hid
    windows = True
except:
    windows = False

import os 
from subprocess import check_output
from Crypto.Cipher import AES
from Crypto import Random
 
 
 
_channel_names = [ 'F3', 'F4', 'P7', 'FC6', 'F7', 'F8','T7','P8','FC5','AF4','T8','O2','O1','FC3']
 
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
quality_bits = [99, 100, 101, 102, 103, 104, 105, 106, 107, 108, 109, 110, 111, 112]

g_battery = 0
#tasks = Queue()



def create_analog_subdevice_param(channel_names):
    n = len(channel_names)
    d = {
                'type' : 'AnalogInput',
                'nb_channel' : n,
                'params' :{  }, 
                'by_channel_params' : { 
                                        'channel_indexes' : range(n),
                                        'channel_names' : channel_names,
                                        }
            }
    return d

def get_info(device_path):
    info = { }
    info['class'] = 'EmotivMultiSignals'
    info['device_path'] = device_path
    
    name = device_path.strip('/dev/')
    realInputPath =  os.path.realpath("/sys/class/hidraw/" + name)
    path = '/'.join(realInputPath.split('/')[:-4])
    with open(path + "/manufacturer", 'r') as f:
        manufacturer = f.readline()
    with open(path + "/serial", 'r') as f:
        serial = f.readline().strip()
    
    info['board_name'] = '{} {}'.format(manufacturer, serial)
    
    
    info['serial'] = serial
    info['global_params'] = {
                                            'sampling_rate' : 128.,
                                            'buffer_length' : 60.,
                                            }
    info['subdevices'] = [ ]
    info['subdevices'].append(create_analog_subdevice_param(_channel_names))
    quality_name = ['Quality {}'.format(n) for n in _channel_names]
    info['subdevices'].append(create_analog_subdevice_param(quality_name))
    info['subdevices'].append(create_analog_subdevice_param([ 'X','Y']))
    
    
    return info


class EmotivMultiSignals(DeviceBase):
    def __init__(self,  **kargs):
        DeviceBase.__init__(self, **kargs)
    
    @classmethod
    def get_available_devices(cls):
        devices = OrderedDict()
        
        
        serials = { }
        for name in os.listdir("/sys/class/hidraw"):
            realInputPath =  os.path.realpath("/sys/class/hidraw/" + name)
            path = '/'.join(realInputPath.split('/')[:-4])
            try:
                with open(path + "/manufacturer", 'r') as f:
                    manufacturer = f.readline()
                if "emotiv" in manufacturer.lower():
                    with open(path + "/serial", 'r') as f:
                        serial = f.readline().strip()
                        if serial not in serials:
                            serials[serial] = [ ]
                        serials[serial].append(name)
            except IOError as e:
                print "Couldn't open file: %s" % e
        
        for serial, names in serials.items():
            device_path = '/dev/'+names[1]
            info = get_info(device_path)
            devices['Emotiv '+device_path] = info
            #~ print d
        
        
        return devices
    
    def configure(self, buffer_length = 60,
                                device_path = '',
                                subdevices = None,
                                ):
        self.params = {'device_path' : device_path,
                                'buffer_length' : buffer_length,
                                'subdevices' : subdevices,
                                }
        self.__dict__.update(self.params)
        self.configured = True        
    
    def initialize(self):
        
        if self.device_path == '':
            # if no device selected take the first one ine the list
            devices = EmotivMultiSignals.get_available_devices()
            self.device_path = devices.values()[0]['device_path']


        info = self.device_info = get_info(self.device_path)
        if self.subdevices is None:
            self.subdevices = info['subdevices']
        
        self.sampling_rate = float(info['global_params']['sampling_rate'])
        self.packet_size = 1
        
        self._os_decryption = False
        
        l = int(self.sampling_rate*self.buffer_length)
        self.buffer_length = (l - l%self.packet_size)/self.sampling_rate
        
        self.name = '{} #{}'.format(info['board_name'], info['serial'])
        
        self.streams = [ ]
        for s, sub in enumerate(self.subdevices):
            stream = self.streamhandler.new_AnalogSignalSharedMemStream(name = self.name+str(s) , sampling_rate = self.sampling_rate,
                                                        nb_channel = sub['nb_channel'], buffer_length = self.buffer_length,
                                                        packet_size = self.packet_size, dtype = np.float64,
                                                        channel_names = sub['by_channel_params']['channel_names'],
                                                        channel_indexes = sub['by_channel_params']['channel_indexes'],
                                                        )            
            self.streams.append(stream)

        
        self.sensors = { }
        for name in _channel_names + ['X', 'Y', 'Unknown']:
            self.sensors[name] = {'value': 0, 'quality': 0}
        


    def start(self):
        
        self.stop_flag = mp.Value('i', 0) #flag pultiproc  = global 
        
        self.setupCrypto( self.device_info['serial'])
        
        s_chan = self.streams[0]
        s_imp = self.streams[1]
        s_gyro = self.streams[2]
        self.process = mp.Process(target = emotiv_mainLoop,  args=(self.stop_flag, s_chan, s_imp, s_gyro, self.device_path, self._os_decryption, self.cipher, self.sensors) )
        self.process.start()
   
        print 'FakeMultiAnalogChannel started:', self.name
        self.running = True


    def stop(self):
        self.stop_flag.value = 1
        self.process.join()
        
        print 'FakeMultiAnalogChannel stopped:', self.name
        self.running = False

    def close(self):
        if windows:
            self.device.close()
        else:
            self._goOn = False
            self.hidraw.close()


    #~ def setupWin(self):
            #~ devices = []
            #~ try:
                #~ for device in hid.find_all_hid_devices():
                    #~ if device.vendor_id != 0x21A1:
                        #~ continue
                    #~ if device.product_name == 'Brain Waves':
                        #~ devices.append(device)
                        #~ device.open()
                        #~ self.serialNum = device.serial_number
                        #~ device.set_raw_data_handler(self.handler)
                    #~ elif device.product_name == 'EPOC BCI':
                        #~ devices.append(device)
                        #~ device.open()
                        #~ self.serialNum = device.serial_number
                        #~ device.set_raw_data_handler(self.handler)
                    #~ elif device.product_name == '00000000000':
                        #~ devices.append(device)
                        #~ device.open()
                        #~ self.serialNum = device.serial_number
                        #~ device.set_raw_data_handler(self.handler)
            #~ finally:
                #~ for device in devices:
                    #~ device.close()


    #~ def setupPosix(self):
        #~ if os.path.exists('/dev/eeg/raw'):
            #~ print("decrpytion handled by the Linux epoc daemon")
            #~ #The decrpytion is handled by the Linux epoc daemon. We don't need to handle it there.
            #~ self._os_decryption = True
            #~ self.hidraw = open("/dev/eeg/raw")
        #~ else:
            #~ setup = self.getLinuxSetup()
            #~ self.serialNum = setup[0]
            #~ if os.path.exists("/dev/" + setup[1]):
                #~ #self.hidraw = open("/dev/" + setup[1])
                #~ self.hidraw = open("/dev/hidraw4")
            #~ else:
                #~ self.hidraw = open("/dev/hidraw4")
            #~ self.setupCrypto( self.serialNum)
            
        #~ print self.hidraw
        #~ print "os_decryption : ",self._os_decryption
        #~ return True
    
    #~ def getLinuxSetup(self):
        #~ rawinputs = []
        #~ for filename in os.listdir("/sys/class/hidraw"):
            #~ realInputPath = check_output(["realpath", "/sys/class/hidraw/" + filename])
            #~ sPaths = realInputPath.split('/')
            #~ s = len(sPaths)
            #~ s = s - 4
            #~ i = 0
            #~ path = ""
            #~ while s > i:
                #~ path = path + sPaths[i] + "/"
                #~ i += 1
            #~ rawinputs.append([path, filename])
        #~ hiddevices = []
        #~ #TODO: Add support for multiple USB sticks? make a bit more elegant
        #~ for input in rawinputs:
            #~ try:
                #~ with open(input[0] + "/manufacturer", 'r') as f:
                    #~ manufacturer = f.readline()
                    #~ f.close()
                #~ if "Emotiv" in manufacturer:  #Emotiv Systems Inc.
                    #~ with open(input[0] + "/serial", 'r') as f:
                        #~ serial = f.readline().strip()
                        #~ f.close()
                    #~ #print "Serial: " + serial + " Device: " + input[1]
                    #~ #Great we found it. But we need to use the second one...
                    #~ hidraw = input[1]
                    #~ id_hidraw = int(hidraw[-1])
                    #~ #The dev headset might use the first device, or maybe if more than one are connected they might.
                    #~ id_hidraw += 1
                    #~ hidraw = "hidraw" + id_hidraw.__str__()
                    #~ print "Serial: " + serial + " Device: " + hidraw + " (Active)"
                    #~ return [serial, hidraw, ]
            #~ except IOError as e:
                #~ print "Couldn't open file: %s" % e


    def setupCrypto(self, sn):
        type = 0 #feature[5]
        type &= 0xF
        type = 0
        #I believe type == True is for the Dev headset, I'm not using that. That's the point of this library in the first place I thought.
        k = ['\0'] * 16
        k[0] = sn[-1]
        k[1] = '\0'
        k[2] = sn[-2]
        if type:
            k[3] = 'H'
            k[4] = sn[-1]
            k[5] = '\0'
            k[6] = sn[-2]
            k[7] = 'T'
            k[8] = sn[-3]
            k[9] = '\x10'
            k[10] = sn[-4]
            k[11] = 'B'
        else:
            k[3] = 'T'
            k[4] = sn[-3]
            k[5] = '\x10'
            k[6] = sn[-4]
            k[7] = 'B'
            k[8] = sn[-1]
            k[9] = '\0'
            k[10] = sn[-2]
            k[11] = 'H'
        k[12] = sn[-3]
        k[13] = '\0'
        k[14] = sn[-4]
        k[15] = 'P'
        #It doesn't make sense to have more than one greenlet handling this as data needs to be in order anyhow. I guess you could assign an ID or something
        #to each packet but that seems like a waste also or is it? The ID might be useful if your using multiple headsets or usb sticks.
        key = ''.join(k)
        iv = Random.new().read(AES.block_size)
        self.cipher = AES.new(key, AES.MODE_ECB, iv)



def emotiv_mainLoop(stop_flag, streamChan, streamImp, streamGyro, device_path, _os_decryption, cipher, sensors,  ):
    import zmq
    pos = 0
    abs_pos = pos2 = 0
    
    
    hidraw = open(device_path)
    
    #Data channels socket
    context = zmq.Context()
    socket_chan = context.socket(zmq.PUB)
    socket_chan.bind("tcp://*:{}".format(streamChan['port']))
    
    #Impedance channels socket
    socket_imp = context.socket(zmq.PUB)
    socket_imp.bind("tcp://*:{}".format(streamImp['port']))
    
    #Gyro channels socket
    socket_gyro = context.socket(zmq.PUB)
    socket_gyro.bind("tcp://*:{}".format(streamGyro['port']))
    
    packet_size = streamChan['packet_size']
    sampling_rate = streamChan['sampling_rate']
    
    np_arr_chan = streamChan['shared_array'].to_numpy_array()
    chanData = np.array(1, dtype = np.int32)
    
    np_arr_imp = streamImp['shared_array'].to_numpy_array()   
    impData = np.array(1, dtype = np.int32)
    
    np_arr_gyro = streamGyro['shared_array'].to_numpy_array()   
    impGyro = np.array(1, dtype = np.int32)
    
    half_size = np_arr_chan.shape[1]/2    # same for the others 
    
    nb_channel = streamChan['nb_channel']
    nb_gyro = streamGyro['nb_channel']
    
    # Linux Style
    while True:
        #~ t1 = time.time()
        try:
            rawData = hidraw.read(32)
            
            if rawData != "":
                if _os_decryption:
                    # TODO check if correct
                    deCryptData =  EmotivPacket(rawData)  #need self.sensors ?
                else:
                    deCryptData = cipher.decrypt(rawData[:16]) + cipher.decrypt(rawData[16:])
                    data =  EmotivPacket(deCryptData, sensors)
        except KeyboardInterrupt:
            print("Data not received")
            stop_flag.value = 1
        
        print data.sensors
        # Get Channels data, impedances and gyro
        #~ for name in 'F3 F4 P7 FC6 F7 F8 T7 P8 FC5 AF4 T8 O2 O1 AF3'.split(' '):	
        for name in _channel_names:
            chanData = np.append(chanData, data.sensors[name]['value'] )
            impData = np.append(impData, data.sensors[name]['quality'] )
        chanData = chanData[-nb_channel:].reshape(nb_channel,1)
        impData = impData[-nb_channel:].reshape(nb_channel,1)
        gyroData = np.array([data.gyroX, data.gyroY]).reshape(nb_gyro,1)
        
        #double copy
        np_arr_chan[:,pos2:pos2+packet_size] = chanData
        np_arr_chan[:,pos2+half_size:pos2+packet_size+half_size] = chanData
        np_arr_imp[:,pos2:pos2+packet_size] = impData
        np_arr_imp[:,pos2+half_size:pos2+packet_size+half_size] = impData
        np_arr_gyro[:,pos2:pos2+packet_size] = gyroData
        np_arr_gyro[:,pos2+half_size:pos2+packet_size+half_size] = gyroData
        
        pos += packet_size
        pos = pos%chanData.shape[1]
        abs_pos += packet_size
        pos2 = abs_pos%half_size
        
        socket_chan.send(msgpack.dumps(abs_pos))
        socket_imp.send(msgpack.dumps(abs_pos))
        socket_gyro.send(msgpack.dumps(abs_pos))
        
        
        if stop_flag.value:
            print 'will stop'
            break
        #~ t2 = time.time()
 

class EmotivPacket(object):
    def __init__(self, data, sensors):
        global g_battery
        self.rawData = data
        self.counter = ord(data[0])
        self.battery = g_battery
        if(self.counter > 127):
            self.battery = self.counter
            g_battery = self.battery_percent()
            self.counter = 128
        self.sync = self.counter == 0xe9
        self.gyroX = ord(data[29]) - 106
        self.gyroY = ord(data[30]) - 105
        sensors['X']['value'] = self.gyroX
        sensors['Y']['value'] = self.gyroY
        for name, bits in sensorBits.items():
            value = self.get_level(self.rawData, bits)
            setattr(self, name, (value,))
            sensors[name]['value'] = value
        self.handle_quality(sensors)
        self.sensors = sensors

    def get_level(self, data, bits):
        level = 0
        for i in range(13, -1, -1):
            level <<= 1
            b, o = (bits[i] / 8) + 1, bits[i] % 8
            level |= (ord(data[b]) >> o) & 1
        return level

    def handle_quality(self, sensors):
        current_contact_quality = self.get_level(self.rawData, quality_bits) / 540
        sensor = ord(self.rawData[0])
        
        num_to_name = { 0 : 'F3',  1:'F5', 2 : 'AF3',  3 : 'F7', 4:'T7', 5 : 'P7', 
                                            6 : 'O1', 7 : 'O2', 8: 'P8', 9 : 'T8', 10: 'F8', 11 : 'AF4', 
                                            12 : 'FC6', 13: 'F4', 14 : 'F8', 15:'AF4', 
                                            64 : 'F3', 65 : 'FC5', 66 : 'AF3', 67 : 'F7', 68 : 'T7', 69 : 'P7', 
                                            70 : 'O1', 71 : 'O2', 72: 'P8', 73 : 'T8', 74: 'F8', 75 : 'AF4', 
                                            76 : 'FC6', 77: 'F4', 78 : 'F8', 79:'AF4', 
                                            80 : 'FC6',
                                            }
        if sensor in num_to_name:
            name = num_to_name[sensor]
            sensors[name]['quality'] = current_contact_quality
        else:
            sensors['Unknown']['quality'] = current_contact_quality
            sensors['Unknown']['value'] = sensor            
        return current_contact_quality

    def battery_percent(self):
        if self.battery > 248:
            return 100
        elif self.battery == 247:
            return 99
        elif self.battery == 246:
            return 97
        elif self.battery == 245:
            return 93
        elif self.battery == 244:
            return 89
        elif self.battery == 243:
            return 85
        elif self.battery == 242:
            return 82
        elif self.battery == 241:
            return 77
        elif self.battery == 240:
            return 72
        elif self.battery == 239:
            return 66
        elif self.battery == 238:
            return 62
        elif self.battery == 237:
            return 55
        elif self.battery == 236:
            return 46
        elif self.battery == 235:
            return 32
        elif self.battery == 234:
            return 20
        elif self.battery == 233:
            return 12
        elif self.battery == 232:
            return 6
        elif self.battery == 231:
            return 4
        elif self.battery == 230:
            return 3
        elif self.battery == 229:
            return 2
        elif self.battery == 228:
            return 2
        elif self.battery == 227:
            return 2
        elif self.battery == 226:
            return 1
        else:
            return 0

    def __repr__(self):
        return 'EmotivPacket(counter=%i, battery=%i, gyroX=%i, gyroY=%i, F3=%i)' % (
            self.counter,
            self.battery,
            self.gyroX,
            self.gyroY,
            self.F3[0],
            )


Emotiv = EmotivMultiSignals















