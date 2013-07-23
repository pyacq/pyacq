# -*- coding: utf-8 -*-

import multiprocessing as mp
import numpy as np
import msgpack
import time

from .base import DeviceBase



def fake_device_mainLoop(stop_flag, stream,  precomputed):
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

    def initialize(self, streamhandler = None):
        self.sampling_rate = float(self.sampling_rate)

        channel_indexes = range(self.nb_channel)
        channel_names = [ 'Channel {}'.format(i) for i in channel_indexes]
        
        s = self.stream = self.streamhandler.new_signals_stream(name = self.name, sampling_rate = self.sampling_rate,
                                                        nb_channel = self.nb_channel, buffer_length = self.buffer_length,
                                                        packet_size = self.packet_size, dtype = np.float64,
                                                        channel_names = channel_names, channel_indexes = channel_indexes,            
                                                        )
        
        arr_size = self.stream['shared_array'].shape[1]
        #~ print arr_size
        #~ print self.arr_size%self.packet_size
        assert (arr_size/2)%self.packet_size ==0, 'buffer should be a multilple of pcket_size {}/2 {}'.format(arr_size, self.packet_size)
        
        # private precomuted array of 20s = some noise + some sinus burst
        n = int(self.sampling_rate*20./self.packet_size)*self.packet_size
        t = np.arange(n, dtype = np.float64)/self.sampling_rate
        self.precomputed = np.random.rand(self.nb_channel, n)
        for i in range(self.nb_channel):
            f1 = np.linspace(np.random.rand()*60+20. , np.random.rand()*60+20., n)
            f2 = np.linspace(np.random.rand()*1.+.1 , np.random.rand()*1.+.1, n)
            self.precomputed[i,:] += np.sin(2*np.pi*t*f1) * np.sin(np.pi*t*f2+np.random.rand()*np.pi)
            self.precomputed[i,:] += np.random.rand()*2. -1  # add random offset
            self.precomputed[i,:] *= np.random.rand()*10 # add random gain
            
            
        print 'FakeMultiAnalogChannel initialized:', self.name, s['port']
    
    def start(self):
        
        self.stop_flag = mp.Value('i', 0)
        
        s = self.stream
        mp_arr = s['shared_array'].mp_array
        self.process = mp.Process(target = fake_device_mainLoop,  args=(self.stop_flag, self.stream, self.precomputed) )
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


