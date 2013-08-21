# -*- coding: utf-8 -*-

import multiprocessing as mp
import numpy as np
import msgpack
import time

import zmq

from pycomedi.device import Device
from pycomedi.subdevice import StreamingSubdevice
from pycomedi.channel import AnalogChannel
from pycomedi.chanspec import ChanSpec
from pycomedi.constant import (AREF, CMDF, INSN, SUBDEVICE_TYPE, TRIG_SRC, UNIT)
from pycomedi.utility import inttrig_insn, Reader, Writer, MMapReader

import mmap

from .base import DeviceBase



def device_mainLoop(stop_flag, streams, device_path, device_info ):
    streamAD = streams[0]

    
    packet_size = streamAD['packet_size']
    sampling_rate = streamAD['sampling_rate']
    arr_ad = streamAD['shared_array'].to_numpy_array()
    channel_indexes = streamAD['channel_indexes']
    
    nb_channel_ad = streamAD['nb_channel']
    half_size = arr_ad.shape[1]/2
    
    context = zmq.Context()
    socketAD = context.socket(zmq.PUB)
    socketAD.bind("tcp://*:{}".format(streamAD['port']))

    dev = Device(device_path)
    dev.open()

    ai_subdevice = dev.find_subdevice_by_type(SUBDEVICE_TYPE.ai, factory=StreamingSubdevice)

    ai_channels = [ ai_subdevice.channel(i, factory=AnalogChannel, aref=AREF.diff) for i in channel_indexes]

    dt = ai_subdevice.get_dtype()
    itemsize = np.dtype(dt).itemsize

    #~ print ai_subdevice.get_max_buffer_size()
    
    internal_size = int(ai_subdevice.get_max_buffer_size()/nb_channel_ad/itemsize)
    ai_subdevice.set_buffer_size(internal_size*nb_channel_ad*itemsize)
    print 'internal_size', internal_size, 'in second', internal_size/sampling_rate/nb_channel_ad/itemsize

    #~ ai_buffer = np.zeros((internal_size, nb_channel_ad), dtype=dt)
    #~ print ai_buffer.shape
    ai_buffer = np.memmap(dev.file, dtype = dt, mode = 'r', shape = (internal_size, nb_channel_ad))
    #~ m = mmap.mmap(dev.fileno(), internal_size*itemsize, flags= mmap.MAP_SHARED, access=  mmap.PROT_READ)
    

    scan_period_ns = int(1e9 / sampling_rate)
    print  sampling_rate, 'real rate',  1e9/scan_period_ns
    ai_cmd = ai_subdevice.get_cmd_generic_timed(len(ai_channels), scan_period_ns)
    ai_cmd.chanlist = ai_channels
    print ai_cmd
    #~ ai_cmd.start_src = TRIG_SRC.int
    #~ ai_cmd.start_arg = 0
    ai_cmd.start_src = TRIG_SRC.now
    ai_cmd.start_arg = 0
    ai_cmd.stop_src = TRIG_SRC.none
    ai_cmd.stop_arg = 0

    ai_subdevice.cmd = ai_cmd
    # test
    for i in range(3):
        rc = ai_subdevice.command_test()
        if rc is not None:
            print 'Not able to command_test properly'
            return

    
    converters = [c.get_converter() for c in ai_channels]
    
    ai_subdevice.command()
    
    
    pos = abs_pos = 0
    last_index = 0
    
    sleep_time = 0.05
    while True:
        #~ try:
        if 1:
            new_bytes =  ai_subdevice.get_buffer_contents()
            # FIXME: Is this util ?
            new_bytes = new_bytes - new_bytes%(nb_channel_ad*itemsize)
            print new_bytes
            
            if new_bytes ==0:
                time.sleep(sleep_time/4.)
                continue
                
            
            index = last_index + new_bytes/nb_channel_ad/itemsize
               
            if index == last_index : 
                time.sleep(sleep_time/4.)
                continue
            
            # buggy???
            #if index>=internal_size:
            #    new_bytes = (internal_size-last_index)*itemsize*nb_channel_ad
            #    index = internal_size
            #
            
            if index>=internal_size:
                new_samp = internal_size - last_index
                new_samp2 = min(new_samp, arr_ad.shape[1]-(pos+half_size))
                for i,c in enumerate(converters):
                    arr_ad[i,pos:pos+new_samp] = c.to_physical(ai_buffer[ last_index:internal_size, i ])
                    arr_ad[i,pos+half_size:pos+new_samp2+half_size] = arr_ad[i,pos:pos+new_samp2]
                
                last_index = 0
                index = index%internal_size
                abs_pos += new_samp
                pos = abs_pos%half_size

            new_samp = index - last_index
            new_samp2 = min(new_samp, arr_ad.shape[1]-(pos+half_size))
            
            #Analog
            for i,c in enumerate(converters):
                arr_ad[i,pos:pos+new_samp] = c.to_physical(ai_buffer[ last_index:index, i ])
                arr_ad[i,pos+half_size:pos+new_samp2+half_size] = arr_ad[i,pos:pos+new_samp2]
                
            
            abs_pos += new_samp
            pos = abs_pos%half_size
            last_index = index%internal_size

            ###TEST avec mmap.read()
            #~ buf = np.fromstring(m.read(new_bytes), dtype=dt)
            #~ new_samp = buf.size/nb_channel_ad
            #~ if new_samp==0: continue
            #~ print buf.shape, new_samp, new_bytes
            #~ buf = buf.reshape(-1, nb_channel_ad)
            #~ new_samp2 = min(new_samp, arr_ad.shape[1]-(pos+half_size))
            #~ for i,c in enumerate(converters):
                #~ arr_ad[i,pos:pos+new_samp] = c.to_physical(buf[ :, i ])
                #~ arr_ad[i,pos+half_size:pos+new_samp2+half_size] = arr_ad[i,pos:pos+new_samp2]
            #~ abs_pos += new_samp
            #~ pos = abs_pos%half_size
            #~ last_index = index%internal_size
            ###test
            
            socketAD.send(msgpack.dumps(abs_pos))
            
            ai_subdevice.mark_buffer_read(new_bytes)
            
        #~ except :
            #~ print 'Problem in acquisition loop'
            #~ break
            
        if stop_flag.value:
            print 'should stop properly'
            break
        
        
    try:
        dev.close()
        print 'has stop properly'
    except :
        print 'not able to stop cbStopBackground properly'



def get_info(device_path):
    info = { }
    dev = Device(device_path)
    dev.open()    
    info['device_path'] = device_path
    info['board_name'] = dev.get_board_name()
    
    ai_subdevice = dev.find_subdevice_by_type(SUBDEVICE_TYPE.ai, factory=StreamingSubdevice)
    info['nb_channel_ad'] = ai_subdevice.get_n_channels()
    info['device_packet_size'] = 512
    dev.close()
    
    return info

class ComediMultiSignals(DeviceBase):
    """
    Usage:
        dev = ComediMultiSignals()
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
        
        return devices

    def configure(self, device_path = '/dev/comedi0',
                                    channel_indexes = None,
                                    channel_names = None,
                                    buffer_length= 10.,
                                    sampling_rate =1000.,
                                    ):
        self.params = {'device_path' : device_path,
                                'channel_indexes' : channel_indexes,
                                'channel_names' : channel_names,
                                'buffer_length' : buffer_length,
                                'sampling_rate' : sampling_rate
                                }
        self.__dict__.update(self.params)
        self.configured = True

    def initialize(self, streamhandler = None):
        
        self.sampling_rate = float(self.sampling_rate)
        
        # TODO card by card
        info = self.device_info = get_info(self.device_path)

        print info
        if self.channel_indexes is None:
            self.channel_indexes = range(info['nb_channel_ad'])
        
        if self.channel_names is None:
            self.channel_names = [ 'AIn Channel {}'.format(i) for i in self.channel_indexes]
        self.nb_channel = len(self.channel_indexes)
        self.packet_size = int(info['device_packet_size']/self.nb_channel)
        print 'self.packet_size', self.packet_size
        
        
        l = int(self.sampling_rate*self.buffer_length)
        #~ print l, l - l%self.packet_size, (l - l%self.packet_size)/self.sampling_rate
        self.buffer_length = (l - l%self.packet_size)/self.sampling_rate
        self.name = '{} #{}'.format(info['board_name'], info['device_path'].replace('/dev/comedi', ''))
        s  = self.streamhandler.new_signals_stream(name = self.name+' Analog', sampling_rate = self.sampling_rate,
                                                        nb_channel = self.nb_channel, buffer_length = self.buffer_length,
                                                        packet_size = self.packet_size, dtype = np.float64,
                                                        channel_names = self.channel_names, channel_indexes = self.channel_indexes,            
                                                        )
        
        
        
        self.streams = [s, ]

    
    def start(self):
        self.stop_flag = mp.Value('i', 0)
        
        self.process = mp.Process(target = device_mainLoop,  args=(self.stop_flag, self.streams, self.device_path, self.device_info) )
        self.process.start()
        
        print 'MeasurementComputingMultiSignals started:', self.name
        self.running = True
    
    def stop(self):
        self.stop_flag.value = 1
        self.process.join()
        print 'MeasurementComputingMultiSignals stopped:', self.name
        
        self.running = False
    
    def close(self):
        pass
        #TODO release stream and close the device


        
        