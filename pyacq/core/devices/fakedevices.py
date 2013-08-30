# -*- coding: utf-8 -*-

import multiprocessing as mp
import numpy as np
import msgpack
import time
from collections import OrderedDict

from .base import DeviceBase


#####
## MultiSignals
def fake_multisignal_mainLoop(stop_flag, stream,  precomputed):
    import zmq
    pos = 0
    abs_pos = pos2 = 0
    
    context = zmq.Context()
    socket = context.socket(zmq.PUB)
    socket.bind("tcp://*:{}".format(stream['port']))
    
    socket.send(msgpack.dumps(abs_pos))
    
    packet_size = stream['packet_size']
    sampling_rate = stream['sampling_rate']
    np_arr = stream['shared_array'].to_numpy_array()
    half_size = np_arr.shape[1]/2
    while True:
        t1 = time.time()
        #~ print 'pos', pos, 'abs_pos', abs_pos
        #double copy
        np_arr[:,pos2:pos2+packet_size] = precomputed[:,pos:pos+packet_size] 
        np_arr[:,pos2+half_size:pos2+packet_size+half_size] = precomputed[:,pos:pos+packet_size]
        pos += packet_size
        pos = pos%precomputed.shape[1]
        abs_pos += packet_size
        pos2 = abs_pos%half_size
        socket.send(msgpack.dumps(abs_pos))
        
        if stop_flag.value:
            print 'will stop'
            break
        t2 = time.time()
        #~ time.sleep(packet_size/sampling_rate-(t2-t1))
        
        time.sleep(packet_size/sampling_rate)
        #~ gevent.sleep(packet_size/sampling_rate)

class FakeMultiSignals(DeviceBase):
    """
    Usage:
        dev = FakeMultiSignals()
        dev.configure(...)
        dev.initialize()
        dev.start()
        dev.stop()
        
    Configuration Parameters:
        nb_channel
        sampling_rate
        buffer_length
        packet_size
        channel_names
        channel_indexes
    
    
    """
    def __init__(self,  **kargs):
        DeviceBase.__init__(self, **kargs)

    @classmethod
    def get_available_devices(cls):
        devices = OrderedDict()
        
        for n in [4,8,16, 64]:
            name = 'fake {} analog input'.format(n)
            info = {'board_name' : name,
                        'class' : 'FakeMultiSignals',
                        'global_params' : {
                                                        'sampling_rate' : 1000.,
                                                        'buffer_length' : 60.,
                                                        'packet_size' : 10,
                                                        },
                        'subdevices' : [ {
                                                    'type' : 'AnalogInput',
                                                    'nb_channel' : n,
                                                    'params' :{  }, 
                                                    'by_channel_params' : { 
                                                                            'ai_channel_indexes' : range(n),
                                                                            'ai_channel_names' : [ 'AI Channel {}'.format(i) for i in range(n)],
                                                        },
                                                },
                            ]
                        }
            devices[name] = info

        return devices
        

    def initialize(self, streamhandler = None):
        self.sampling_rate = float(self.sampling_rate)

        channel_indexes = range(self.nb_channel)
        channel_names = [ 'Channel {}'.format(i) for i in channel_indexes]

        l = int(self.sampling_rate*self.buffer_length)
        self.buffer_length = (l - l%self.packet_size)/self.sampling_rate
        
        s = self.streamhandler.new_AnalogSignalSharedMemStream(name = self.name, sampling_rate = self.sampling_rate,
                                                        nb_channel = self.nb_channel, buffer_length = self.buffer_length,
                                                        packet_size = self.packet_size, dtype = np.float64,
                                                        channel_names = channel_names, channel_indexes = channel_indexes,            
                                                        )
        
        self.streams = [s, ]
        
        arr_size = s['shared_array'].shape[1]
        assert (arr_size/2)%self.packet_size ==0, 'buffer should be a multilple of pcket_size {}/2 {}'.format(arr_size, self.packet_size)
        
        # private precomuted array of 20s = some noise + some sinus burst
        n = int(self.sampling_rate*20./self.packet_size)*self.packet_size
        t = np.arange(n, dtype = np.float64)/self.sampling_rate
        self.precomputed = np.random.rand(self.nb_channel, n)
        for i in range(self.nb_channel):
            f1 = np.linspace(np.random.rand()*60+20. , np.random.rand()*60+20., n)
            f2 = np.linspace(np.random.rand()*1.+.1 , np.random.rand()*1.+.1, n)
            self.precomputed[i,:] += np.sin(2*np.pi*t*f1) * np.sin(np.pi*t*f2+np.random.rand()*np.pi)
            self.precomputed[i,:] += np.random.rand()*40. -20  # add random offset
            self.precomputed[i,:] *= np.random.rand()*10 # add random gain
            
            
        print 'FakeMultiAnalogChannel initialized:', self.name, s['port']
    
    def start(self):
        
        self.stop_flag = mp.Value('i', 0) #flag pultiproc
        
        s = self.streams[0]
        mp_arr = s['shared_array'].mp_array
        self.process = mp.Process(target = fake_multisignal_mainLoop,  args=(self.stop_flag, s, self.precomputed) )
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
        #TODO release stream and close the device



#####
## MultiSignals
def fake_digital_mainLoop(stop_flag, stream,  precomputed):
    import zmq
    pos = 0
    abs_pos = pos2 = 0
    
    context = zmq.Context()
    socket = context.socket(zmq.PUB)
    socket.bind("tcp://*:{}".format(stream['port']))
    
    packet_size = stream['packet_size']
    sampling_rate = stream['sampling_rate']
    np_arr = stream['shared_array'].to_numpy_array()
    half_size = np_arr.shape[1]/2
    while True:
        t1 = time.time()
        #~ print 'pos', pos, 'abs_pos', abs_pos
        #double copy
        np_arr[:,pos2:pos2+packet_size] = precomputed[:,pos:pos+packet_size] 
        np_arr[:,pos2+half_size:pos2+packet_size+half_size] = precomputed[:,pos:pos+packet_size]
        pos += packet_size
        pos = pos%precomputed.shape[1]
        abs_pos += packet_size
        pos2 = abs_pos%half_size
        socket.send(msgpack.dumps(abs_pos))
        
        if stop_flag.value:
            print 'will stop'
            break
        t2 = time.time()
        #~ time.sleep(packet_size/sampling_rate-(t2-t1))
        
        time.sleep(packet_size/sampling_rate)
        #~ gevent.sleep(packet_size/sampling_rate)



class FakeDigital(DeviceBase):
    """
    
    
    """
    def __init__(self,  **kargs):
        DeviceBase.__init__(self, **kargs)
        
    
    @classmethod
    def get_available_devices(cls):
        devices = OrderedDict()
        
        for n in [8, 32]:
            name = 'fake {} digital input'.format(n)
            info = {'board_name' : name,
                        'class' : 'FakeDigital',
                        'global_params' : {
                                                    'sampling_rate' : 1000.,
                                                    'buffer_length' : 60.,
                                                    'packet_size' : 10,
                                                    },
                        'subdevices' : [ {
                                                    'type' : 'DigitalInput',
                                                    'nb_channel' : n,
                                                    'params' :{ },
                                                    'by_channel_params' : { 
                                                                            'di_channel_indexes' : range(n),
                                                                            'di_channel_names' : [ 'DI Channel {}'.format(i) for i in range(n)],
                                                        },
                                                },
                            ]
                        }
            devices[name] = info

        return devices
    def initialize(self, streamhandler = None):
        self.sampling_rate = float(self.sampling_rate)

        channel_names = [ 'Channel {}'.format(i) for i in range(self.nb_channel)]

        l = int(self.sampling_rate*self.buffer_length)
        self.buffer_length = (l - l%self.packet_size)/self.sampling_rate
        
        s = self.streamhandler.new_DigitalSignalSharedMemStream(name = self.name, sampling_rate = self.sampling_rate,
                                                        nb_channel = self.nb_channel, buffer_length = self.buffer_length,
                                                        packet_size = self.packet_size, channel_names = channel_names)
        
        self.streams = [s, ]
        
        arr_size = s['shared_array'].shape[1]
        assert (arr_size/2)%self.packet_size ==0, 'buffer should be a multilple of pcket_size {}/2 {}'.format(arr_size, self.packet_size)
        
        # private precomuted array of 20s = each channel have a diffrent period
        n = int(self.sampling_rate*20./self.packet_size)*self.packet_size
        t = np.arange(n, dtype = np.float64)/self.sampling_rate
        #~ self.precomputed = np.random.rand(s['shared_array'].shape[0], n)
        self.precomputed = np.zeros((s['shared_array'].shape[0], n), dtype = np.uint8)
        for i in range(self.nb_channel):
            b = i//8
            mask =  1 << i%8
            
            cycle_size = int((i+1)*self.sampling_rate/2)
            #~ print i, b, mask, cycle_size
            period = np.concatenate([np.ones(cycle_size, dtype = np.uint8), np.zeros(cycle_size, dtype = np.uint8)] * (1+n/cycle_size/2))[:n]
            #~ self.precomputed[b, :period.size] = self.precomputed[b, :period.size] + period*mask
            self.precomputed[b, :] = self.precomputed[b, :] + period*mask
            #~ print (period*mask)[:cycle_size*2]
            #~ print self.precomputed[b,:cycle_size*2]
            #~ print n , period.size
        #~ print 'FakeDigital initialized:', self.name, s['port']
    
    def start(self):
        
        self.stop_flag = mp.Value('i', 0) #flag pultiproc
        
        s = self.streams[0]
        mp_arr = s['shared_array'].mp_array
        self.process = mp.Process(target = fake_digital_mainLoop,  args=(self.stop_flag, s, self.precomputed) )
        self.process.start()
        
        #~ print 'FakeDigital started:', self.name
        self.running = True
    
    def stop(self):
        self.stop_flag.value = 1
        self.process.join()
        #~ print 'FakeDigital stopped:', self.name
        
        self.running = False
    
    def close(self):
        pass
        #TODO release stream and close the device

