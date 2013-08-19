# -*- coding: utf-8 -*-

import multiprocessing as mp
import numpy as np
import msgpack
import time

import zmq

import os
from collections import OrderedDict

from .base import DeviceBase
#~ from ..tools import SharedArray

import ctypes
from ctypes import byref


## Wrapper on Universal Library with ctypes with error handling
try:
    _cbw = ctypes.windll.cbw32
    print 'cbw32'
except WindowsError:
    _cbw = ctypes.windll.cbw64
    #~ _cbw = ctypes.WinDLL('cbw64.dll')
    print 'cbw64'

class ULError( Exception ):
    def __init__(self, errno):
        self.errno = errno
        err_msg = ctypes.create_string_buffer(UL.ERRSTRLEN)
        errno2 = _cbw.cbGetErrMsg(errno,err_msg)
        assert errno2==0, Exception('_cbw.cbGetErrMsg do not work')
        errstr = 'ULError %d: %s'%(errno,err_msg.value)                
        Exception.__init__(self, errstr)

def decorate_with_error(f):
    def func_with_error(*args):
        errno = f(*args)
        if errno!=UL.NOERRORS:
            raise ULError(errno)
        return errno
    return func_with_error

class CBW:
    def __getattr__(self, attr):
        f = getattr(_cbw, attr)
        return decorate_with_error(f)

cbw = CBW()    
##



def device_mainLoop(stop_flag, streams, board_num, ul_dig_ports ):
    streamAD = streams[0]
    streamDIG = streams[1]
    
    packet_size = streamAD['packet_size']
    sampling_rate = streamAD['sampling_rate']
    arr_ad = streamAD['shared_array'].to_numpy_array()
    
    nb_channel_ad = streamAD['nb_channel']
    half_size = arr_ad.shape[1]/2
    
    nb_port_dig = len(ul_dig_ports)
    arr_dig = streamDIG['shared_array'].to_numpy_array()
    
    nb_total_channel = streamAD['nb_channel'] + nb_port_dig
    
    context = zmq.Context()
    socketAD = context.socket(zmq.PUB)
    socketAD.bind("tcp://*:{}".format(streamAD['port']))

    socketDIG = context.socket(zmq.PUB)
    socketDIG.bind("tcp://*:{}".format(streamDIG['port']))
    
    print 'ul_dig_ports', ul_dig_ports
    
    chan_array = np.array( streamAD['channel_indexes']+ul_dig_ports, dtype = np.int16)
    chan_array_type = np.array( [UL.ANALOG] * nb_channel_ad +[ UL.DIGITAL8] *nb_port_dig  , dtype = np.int16)
    gain_array = np.array( [UL.BIP10VOLTS] *nb_channel_ad + [0] *nb_port_dig, dtype = np.int16)
    real_sr = ctypes.c_long(int(sampling_rate))

    internal_size = int(30.*sampling_rate)
    internal_size = internal_size- internal_size%packet_size
    
    raw_arr = np.zeros(( internal_size, nb_total_channel), dtype = np.uint16)
    pretrig_count = ctypes.c_long(0)
    total_count = ctypes.c_long(int(raw_arr.size))
    # FIXME try with other card
    #~ options = UL.BACKGROUND + UL.BLOCKIO  + UL.CONTINUOUS + UL.CONVERTDATA
    #~ options = UL.BACKGROUND + UL.DMAIO  + UL.CONTINUOUS + UL.CONVERTDATA
    options = UL.BACKGROUND  + UL.CONTINUOUS + UL.CONVERTDATA
    
    try:
        # this is SLOW!!!!:
        cbw.cbDaqInScan(board_num, chan_array.ctypes.data,  chan_array_type.ctypes.data,
                            gain_array.ctypes.data, nb_total_channel, byref(real_sr), byref(pretrig_count),
                             byref(total_count) ,raw_arr.ctypes.data, options)
        #~ cbw.cbAInScan(board_num, 0, nb_channel-1, int(int16_arr.size),
              #~ ctypes.byref(real_sr), gain, int16_arr.ctypes.data, options)
                             
    except ULError as e:
        print 'Not able to cbDaqInScan properly', e
        return
        #TODO : retry when bacground already running.
    
    status = ctypes.c_int(0)
    cur_count = ctypes.c_long(0)
    cur_index = ctypes.c_long(0)
    function = UL.DAQIFUNCTION
    
    # TODO this
    dict_gain = {UL.BIP10VOLTS: [-10., 10.],
                        UL.BIP1VOLTS: [-1., 1.],
                        }
    low_range = np.array([ dict_gain[g][0] for g in gain_array[:nb_channel_ad] ])
    hight_range = np.array([ dict_gain[g][1] for g in gain_array[:nb_channel_ad] ])
    buffer_gains = 1./(2**16)*(hight_range-low_range)
    buffer_gains = buffer_gains[ :, np.newaxis]
    buffer_offsets = low_range
    buffer_offsets = buffer_offsets[ :, np.newaxis]
    
    pos = abs_pos = 0
    last_index = 0
    ad_mask = np.zeros(nb_total_channel, dtype = bool)
    ad_mask[:nb_channel_ad] = True
    dig_mask = ~ad_mask
    
    while True:
        try:
        #~ if True:
            cbw.cbGetIOStatus( ctypes.c_int(board_num), byref(status),
                      byref(cur_count), byref(cur_index), ctypes.c_int(function))
            
            index = cur_index.value/nb_total_channel
            if index ==-1: continue
            if index == last_index : 
                continue
            t1 = time.time()
            if index<last_index:
                new_size = raw_arr.shape[0] - last_index
                
                #Analog
                arr_ad[:,pos:pos+new_size] = raw_arr[last_index:, ad_mask].transpose()
                arr_ad[:,pos:pos+new_size] *= buffer_gains
                arr_ad[:,pos:pos+new_size] += buffer_offsets
                
                end = min(pos+half_size+new_size, arr_ad.shape[0])
                new_size2 = min(new_size, arr_ad.shape[1]-(pos+half_size))
                arr_ad[:,pos+half_size:pos+half_size+new_size2] = raw_arr[ last_index:last_index+new_size2, ad_mask].transpose()
                arr_ad[:,pos+half_size:pos+half_size+new_size2] *= buffer_gains
                arr_ad[:,pos+half_size:pos+half_size+new_size2] += buffer_offsets
                
                # Digital
                arr_dig[:,pos:pos+new_size] = raw_arr[last_index:, dig_mask].transpose().astype(np.uint8)
                arr_dig[:,pos+half_size:pos+half_size+new_size2] = raw_arr[ last_index:last_index+new_size2, dig_mask].transpose().astype(np.uint8)
                
                abs_pos += new_size
                pos = abs_pos%half_size
                last_index = 0
            new_size = index - last_index
            
            #Analog
            arr_ad[:,pos:pos+new_size] = raw_arr[ last_index:index, ad_mask ].transpose()
            arr_ad[:,pos:pos+new_size] *= buffer_gains
            arr_ad[:,pos:pos+new_size] += buffer_offsets
            
            new_size2 = min(new_size, arr_ad.shape[1]-(pos+half_size))
            arr_ad[:,pos+half_size:pos+new_size2+half_size] = raw_arr[ last_index:last_index+new_size2, ad_mask ].transpose()
            arr_ad[:,pos+half_size:pos+new_size2+half_size] *= buffer_gains
            arr_ad[:,pos+half_size:pos+new_size2+half_size] += buffer_offsets
            
            
            # Digital
            arr_dig[:,pos:pos+new_size] = raw_arr[ last_index:index, dig_mask ].transpose().astype(np.uint8)
            arr_dig[:,pos+half_size:pos+new_size2+half_size] = raw_arr[ last_index:last_index+new_size2, dig_mask ].transpose().astype(np.uint8)
            
            abs_pos += new_size
            pos = abs_pos%half_size
            last_index = index

            
            socketAD.send(msgpack.dumps(abs_pos))
            socketDIG.send(msgpack.dumps(abs_pos))


            
            last_index = index
        except ULError as e:
            print 'Problem ULError in acquisition loop', e
            break
        except :
            print 'Problem in acquisition loop'
            break
            
        if stop_flag.value:
            print 'should stop properly'
            break
        t2 = time.time()
        #~ time.sleep(packet_size/sampling_rate)
        #~ print t2-t1, max(packet_size/sampling_rate-(t2-t1) , 0) , packet_size/sampling_rate
        #~ print 'sleep', packet_size/sampling_rate-(t2-t1), packet_size/sampling_rate, t2-t1
        time.sleep(max(packet_size/sampling_rate-(t2-t1), 0))
        #~ print 'half sleep'
        
    try:
        cbw.cbStopBackground(board_num, function)
        print 'has stop properly'
    except ULError:
        print 'not able to stop cbStopBackground properly'
        



def get_info(board_num):
    
    config_val = ctypes.c_int(0)
    l = [ ('nb_channel_ad', UL.BOARDINFO, UL.BINUMADCHANS),
                ('nb_channel_da', UL.BOARDINFO, UL.BINUMDACHANS),
                ('BINUMIOPORTS', UL.BOARDINFO, UL.BINUMIOPORTS),
                ('nb_channel_dig', UL.BOARDINFO, UL.BIDINUMDEVS),
                ('serial_num', UL.BOARDINFO, UL.BISERIALNUM),
                ('factory_id', UL.BOARDINFO, UL.BIFACTORYID),
                ]
    info = {'board_num' : board_num}
    board_name = ctypes.create_string_buffer(UL.BOARDNAMELEN)
    cbw.cbGetBoardName(board_num, byref(board_name))# this is very SLOW!!!!!!!
    
    info['board_name'] = board_name.value
    for name, info_type, config_item in l:
        cbw.cbGetConfig(info_type, board_num, 0, config_item, byref(config_val))
        info[name] = config_val.value
    
    dict_packet_size = 	{
                "USB-1616FS"  : 62,
                "USB-1208LS" : 64,
                "USB-1608FS" : 31,
                'PCI-1602/16' : 64,
                }
    info['device_packet_size'] = dict_packet_size.get(info['board_name'], 512)
    
    return info

class MeasurementComputingMultiSignals(DeviceBase):
    """
    Usage:
        dev = MeasurementComputingMultiSignals()
        dev.configure(board_num = 0)
        dev.initialize()
        dev.start()
        dev.stop()
        
    Configuration Parameters:
        board_num
        sampling_rate
        buffer_length
        channel_names
        channel_indexes
    """
    def __init__(self,  **kargs):
        DeviceBase.__init__(self, **kargs)
    
    @classmethod
    def get_available_devices(cls):
        print cls
        devices = OrderedDict()
        
        
        config_val = ctypes.c_int(0)
        cbw.cbGetConfig(UL.GLOBALINFO, 0, 0, UL.GINUMBOARDS, byref(config_val))
        board_nums = config_val.value
        for board_num in range(board_nums):
            try:
                info = get_info(board_num)
                devices[board_num] = info
            except ULError:
                pass
        
        return devices

    def configure(self, board_num = 0, 
                                    channel_indexes = None,
                                    channel_names = None,
                                    digital_port = None,
                                    dig_channel_names = None,
                                    buffer_length= 5.12,
                                    sampling_rate =1000.,
                                    
                                    ):
        self.params = {'board_num' : board_num,
                                'channel_indexes' : channel_indexes,
                                'channel_names' : channel_names,
                                'digital_port' : digital_port,
                                'dig_channel_names' : dig_channel_names,
                                'buffer_length' : buffer_length,
                                'sampling_rate' : sampling_rate
                                }
        self.__dict__.update(self.params)
        self.configured = True

    def initialize(self, streamhandler = None):
        
        self.sampling_rate = float(self.sampling_rate)
        
        # TODO card by card
        info = self.device_info = get_info(self.board_num)
        
        if self.channel_indexes is None:
            self.channel_indexes = range(info['nb_channel_ad'])
        if self.channel_names is None:
            self.channel_names = [ 'Channel {}'.format(i) for i in self.channel_indexes]
        self.nb_channel = len(self.channel_indexes)
        self.packet_size = int(info['device_packet_size']/self.nb_channel)
        print 'self.packet_size', self.packet_size
        
        
        l = int(self.sampling_rate*self.buffer_length)
        self.buffer_length = (l - l%self.packet_size)/self.sampling_rate
        self.name = '{} #{}'.format(info['board_name'], info['factory_id'])
        s  = self.streamhandler.new_signals_stream(name = self.name+' Analog', sampling_rate = self.sampling_rate,
                                                        nb_channel = self.nb_channel, buffer_length = self.buffer_length,
                                                        packet_size = self.packet_size, dtype = np.float64,
                                                        channel_names = self.channel_names, channel_indexes = self.channel_indexes,            
                                                        )
        
        
        # Digital
        if self.digital_port is None:
            self.digital_port = range(info['nb_channel_dig'])
        print self.digital_port
        all_ports = [ UL.FIRSTPORTA, UL.FIRSTPORTB, UL.FIRSTPORTC]
        port_names = ['A', 'B', 'C' ]
        self.ul_dig_ports = [ all_ports[p] for p in self.digital_port]
        if self.dig_channel_names is None:
            self.dig_channel_names = [ '{} {}'.format(port_names[p], c) for p in self.digital_port  for c in range(8) ]
        print self.dig_channel_names
        s2 = self.streamhandler.new_digital_stream(name = self.name+' Digital', sampling_rate = self.sampling_rate,
                                                        nb_channel = len(self.digital_port)*8, buffer_length = self.buffer_length,
                                                        packet_size = self.packet_size, channel_names = self.dig_channel_names)
        
        self.streams = [s, s2 ]

        arr_size = s['shared_array'].shape[1]
        assert (arr_size/2)%self.packet_size ==0, 'buffer should be a multilple of pcket_size {}/2 {}'.format(arr_size, self.packet_size)
        
        
    
    def start(self):
        self.stop_flag = mp.Value('i', 0)
        
        self.process = mp.Process(target = device_mainLoop,  args=(self.stop_flag, self.streams, self.board_num, self.ul_dig_ports) )
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



def generate_ULconstants():
    print 'generate_ULconstants' 
    print __file__
    print os.path.dirname(__file__)
    target = os.path.join(os.path.dirname(__file__), 'ULconstants.py')
    source = os.path.join(os.path.dirname(__file__), 'cbw.h')
    assert os.path.exists(source), 'Put cbw.h file in the pyacq/core/device'

    import re

    fid = open(target,'w')
    fid.write('# this file is generated : do not modify\n')
    for line in open(source,'r').readlines():
        #~ if 'cb' in line:
            #~ continue
        if '#define cbGetStatus cbGetIOStatus' in line :
            continue
        if '#define cbStopBackground cbStopIOBackground' in line :
            continue
        if 'float' in line or 'int' in line or 'char' in line or 'long' in line or 'short' in line \
                or 'HGLOBAL' in line \
                or 'USHORT' in line or 'LONG' in line  \
                or '#endif' in line or  '#undef' in line or  '#endif' in line \
                or 'EXTCCONV' in line :
            continue
        
        r = re.findall('#define[ \t]*(\S*)[ \t]*(\S*)[ \t]*/\* ([ \S]+) \*/',line)
        if len(r) >0:
            fid.write('%s    =    %s    # %s \n'%r[0])
            continue

        r = re.findall('#define[ \t]*(\S*)[ \t]*(\S*)[ \t]*',line)
        if len(r) >0:
            fid.write('%s    =    %s    \n'%r[0])
            continue

        r = re.findall('/\* ([ \S]+) \*/',line)
        if len(r) >0:
            comments = r[0]
            fid.write('# %s \n'%comments)
            continue
        
        if line == '\r\n':
            fid.write('\n')
            continue
        
        if '(' in line and ')' in line :
            continue
        #~ print len(line),line
    fid.close()

try :
    from  . import ULconstants as UL
except:
    generate_ULconstants()
    #~ import .ULconstants as UL 
    from  . import ULconstants as UL



