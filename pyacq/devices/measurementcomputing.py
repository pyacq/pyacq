import numpy as np
import time
import logging

import ctypes
from ctypes import byref

from pyqtgraph.Qt import QtCore, QtGui

from ..core import Node, register_node_type
from  . import ULconstants as UL

"""
Note:
this should was written to wrap cbw dll with ctypes.
Now measurement computing provide an official python
wrapper (also based on ctypes) here https://github.com/mccdaq

This should be maybe rewritten using it but at the same time
measurement computing also provide another libray uldaq
(https://github.com/mccdaq/uldaq) for linux with another
python wrapper.

Waiting for MC unifing something crossplatform I prefer
to keep this old but tested code.

"""



try:
    _cbw = ctypes.windll.cbw32
    HAVE_MC = True
    #~ print('cbw32')
except WindowsError:
    try:
        _cbw = ctypes.windll.cbw64
        HAVE_MC = True
        #~ print('cbw64')
    except:
        HAVE_MC = False

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

if HAVE_MC:
    cbw = CBW()    


class MeasurementComputing(Node):
    """
    """
    _output_specs = {'signals' : dict(streamtype = 'analogsignal',
                    dtype = 'uint16', shape = (-1, 16), compression ='',
                    time_axis=0, sampling_rate =30.),
                    'digital' : dict(streamtype = 'digitalsignal',
                    dtype = 'uint16', shape = (-1, 8), compression ='',
                    time_axis=0, sampling_rate =30.),
                    }

    def __init__(self, **kargs):
        Node.__init__(self, **kargs)
        assert HAVE_MC, "MeasurementComputing depend on MeasurementComputing DLL"

    def _configure(self, board_num = 0, sampling_rate = 1000., 
            timer_interval = 100, subdevices_params = None):
        self.board_num = int(board_num)
        self.sampling_rate = sampling_rate
        self.timer_interval = timer_interval
        if subdevices_params is None:
            # scan_device_info give the default params
            subdevices_params = self.scan_device_info(board_num)['subdevices']
        self.subdevices_params = subdevices_params
        
        self.prepare_device()
        
        self.outputs['signals'].spec['shape'] = (-1, self.nb_ai_channel)
        self.outputs['signals'].spec['dtype = '] = 'uint16'
        self.outputs['signals'].spec['sampling_rate'] = self.real_sampling_rate
        
        #TODO gain by channels
        self.outputs['signals'].spec['gain'] = 1.
        self.outputs['signals'].spec['offset'] = 0.

        self.outputs['digital'].spec['shape'] = (-1, self.info['nb_di_port'])
        self.outputs['digital'].spec['dtype = '] = 'uint16'
        self.outputs['digital'].spec['sampling_rate'] = self.real_sampling_rate
        self.outputs['digital'].spec['gain'] = 1
        self.outputs['digital'].spec['offset'] = 0

    def _initialize(self):
        
        self.timer = QtCore.QTimer(singleShot = False, interval = self.timer_interval)
        self.timer.timeout.connect(self.periodic_poll)

        self.head = 0
        self.last_index = 0

        self.ai_mask = np.zeros(self.nb_total_channel, dtype = bool)
        self.ai_mask[:self.nb_ai_channel] = True
        self.di_mask = ~self.ai_mask
        
    
    def _start(self):
        self._start_daq_scan()
        #~ try:
            #~ self._start_daq_scan()
        #~ except ULError as e:
            #~ if e.errno == 35:
                #~ #do not known why sometimes just a second try and it is OK
                #~ time.sleep(1.)
                #~ self._start_daq_scan()
            #~ elif e.errno == UL.BADBOARDTYPE :
                #~ logging.info(self.info['board_name'], 'do not support cbDaqInScan')
                #~ raise()
        self.timer.start()

    def _start_daq_scan(self):
        if self.mode_daq_scan == 'cbAInScan':
            low_chan = int(min(self.ai_channel_index))
            high_chan = int(max(self.ai_channel_index))
            #~ print(self.raw_arr.ctypes.data)
            #~ print(self.raw_arr.__array_interface__['data'])
            

            cbw.cbAInScan(self.board_num, low_chan, high_chan, ctypes.c_long(self.raw_arr.size),
                  ctypes.byref(self.real_sr), ctypes.c_int(self.gain_array[0]),
                    ctypes.c_void_p(self.raw_arr.ctypes.data), self.options)
            self.function = UL.AIFUNCTION
        elif self.mode_daq_scan == 'cbDaqInScan':
            cbw.cbDaqInScan(self.board_num, self.chan_array.ctypes.data,
                self.chan_array_type.ctypes.data, self.gain_array.ctypes.data,
                self.nb_total_channel, byref(self.real_sr), byref(self.pretrig_count),
                byref(self.total_count), self.raw_arr.ctypes.data, self.options)
            self.function = UL.DAQIFUNCTION

    def _stop(self):
        self.timer.stop()
        if self.mode_daq_scan == 'cbAInScan':
            cbw.cbStopBackground(ctypes.c_int(self.board_num))
        elif self.mode_daq_scan == 'cbDaqInScan':
            cbw.cbStopBackground(ctypes.c_int(self.board_num), ctypes.c_int(self.function))
    
    def _close(self):
        del self.raw_arr

    def scan_device_info(self, board_num):
        info = { }
        
        config_val = ctypes.c_int(0)
        board_name = ctypes.create_string_buffer(UL.BOARDNAMELEN)
        cbw.cbGetBoardName(board_num, byref(board_name))
        info['board_name'] = board_name.value
        l = [ 
                ('board_type', UL.BOARDINFO, UL.BIBOARDTYPE),
                ('nb_ai_channel', UL.BOARDINFO, UL.BINUMADCHANS),
                ('nb_ao_channel', UL.BOARDINFO, UL.BINUMDACHANS),
                #~ ('BINUMIOPORTS', UL.BOARDINFO, UL.BINUMIOPORTS),
                ('nb_di_port', UL.BOARDINFO, UL.BIDINUMDEVS),
                ('serial_num', UL.BOARDINFO, UL.BISERIALNUM),
                ('factory_id', UL.BOARDINFO, UL.BIFACTORYID),
                ]
        for key, info_type, config_item in l:
            cbw.cbGetConfig(info_type, board_num, 0, config_item,
                    byref(config_val))
            info[key] = config_val.value
        
        
        #~ (b'USB-1616FS', b'USB-1208LS', b'USB-1608FS', b'USB-1608FS-Plus'
        
        #~ if info['board_type'] in [122, 125]:
        if info['board_name'] in [b'USB-1208LS']:
            info['packet_size'] = 64
        #~ elif info['board_type'] in [130, 161, 240, 125]:
        elif info['board_name'] in [b'USB-1208FS', b'USB-1408FS', b'USB-7204',  b'USB-1608FS']:
            info['packet_size'] = 31
        else:
            info['packet_size'] = 1

        info['device_params'] = { 'board_num': board_num, 
                                    'sampling_rate' : 1000.,}
        
        info['subdevices'] = [ ]
        if info['nb_ai_channel']>0:
            n = info['nb_ai_channel']
            info_sub = {'type' : 'AnalogInput', 'nb_channel' : n,
                    'subdevice_params' :{}, 
                        'by_channel_params' : [ {'channel_index' : i,
                        'selected' : True, } for i in range(n)] }
            info['subdevices'].append(info_sub)
        
        info['list_di_port'] = []
        if info['nb_di_port']>0:
            n = 0
            for num_dev in range(info['nb_di_port']):
                cbw.cbGetConfig(UL.DIGITALINFO, board_num, num_dev,
                                        UL.DIDEVTYPE, byref(config_val))
                didevtype =   config_val.value
                cbw.cbGetConfig(UL.DIGITALINFO, board_num, num_dev,
                                        UL.DINUMBITS, byref(config_val))
                nbits = config_val.value
                
                # FIXME deal only with 8 bits at the moment
                if didevtype==UL.AUXPORT or nbits!=8: 
                    info['nb_di_port'] -= 1
                else:
                    n += nbits
                    info['list_di_port'].append(didevtype)
            
            if n>0:
                info_sub = {'type' : 'DigitalInput', 'nb_channel' : n,
                    'subdevice_params' :{}, 
                    'by_channel_params' : [ {'channel_index' : i }
                         for i in range(n)] }
                info['subdevices'].append(info_sub)
        
        return info
    
    def prepare_device(self):
        self.info = self.scan_device_info(self.board_num)
        
        #analog input
        ai_info = self.subdevices_params[0]
        self.ai_channel_index = [ p['channel_index'] for p in\
                    ai_info['by_channel_params'] if p['selected'] ]
        self.nb_ai_channel = len(self.ai_channel_index)
        
        #digital input
        if self.info['nb_di_port']>0:
            di_info = self.subdevices_params[1]
            self.nb_di_port = self.info['nb_di_port']
            self.nb_di_channel = di_info['nb_channel']
        
        self.nb_total_channel = self.nb_ai_channel + self.info['nb_di_port']

        self.chan_array = np.array(self.ai_channel_index +\
                    self.info['list_di_port'], dtype = 'int16')
        self.chan_array_type = np.array( [UL.ANALOG] * self.nb_ai_channel +\
                    [ UL.DIGITAL8] * self.info['nb_di_port'], dtype = np.int16)
        self.gain_array = np.array( [UL.BIP10VOLTS] *self.nb_ai_channel +\
                    [0] * self.info['nb_di_port'], dtype = np.int16)
        self.real_sr = ctypes.c_long(int(self.sampling_rate))

        self.internal_size = int(10.*self.sampling_rate) # buffer of 10S
        self.internal_size = self.internal_size - self.internal_size%(self.info['packet_size'])

        self.raw_arr = np.zeros(( self.internal_size, self.nb_total_channel), dtype = 'uint16')
        self.pretrig_count = ctypes.c_long(0)
        self.total_count = ctypes.c_long(int(self.raw_arr.size))
        self.options = ctypes.c_int(UL.BACKGROUND  + UL.CONTINUOUS + UL.CONVERTDATA)
        
        # TODO get the real sampling_rate here : maybe a start/stop
        self.real_sampling_rate = self.sampling_rate
        
        if self.info['board_name'] in (b'USB-1616FS', b'USB-1208LS', b'USB-1608FS', b'USB-1608FS-Plus'):
            #for some old card the scanning mode is limited
            self.mode_daq_scan = 'cbAInScan'
            assert np.all(np.diff(self.ai_channel_index) == 1), 'For this card you must select continuous cannel indexes'
            assert self.info['nb_di_port'] ==0, 'You can not sample digital ports'
            assert np.all(self.gain_array[0]==self.gain_array), 'For this card gain must be identical'
        else:
            self.mode_daq_scan = 'cbDaqInScan'
    
    def periodic_poll(self):
        status = ctypes.c_int(0)
        cur_count = ctypes.c_long(0)
        cur_index = ctypes.c_long(0)
        
        cbw.cbGetIOStatus( ctypes.c_int(self.board_num), byref(status),
            byref(cur_count), byref(cur_index), ctypes.c_int(self.function))
        
        
        if cur_index.value==-1: 
            return
        
        index = cur_index.value // self.nb_total_channel
        
        if index == self.last_index :
            return
        
        
        if index<self.last_index:
            #end of internal ring
            new_samp = self.internal_size - self.last_index
            self.head += new_samp
            self.outputs['signals'].send(self.head, self.raw_arr[self.last_index:, self.ai_mask])
            if self.info['nb_di_port']>0:
                self.outputs['digital'].send(self.head, self.raw_arr[self.last_index:, self.di_mask])
            self.last_index = 0
        
        new_samp = index - self.last_index
        self.head += new_samp
        self.outputs['signals'].send(self.head, self.raw_arr[ self.last_index:index, self.ai_mask])
        if self.info['nb_di_port']>0:
            self.outputs['digital'].send(self.head, self.raw_arr[ self.last_index:index, self.di_mask])
        
        self.last_index = index%self.internal_size
        

register_node_type(MeasurementComputing)


def generate_ULconstants():
    # very old hoem made parser, need to be rewritten
    print('generate_ULconstants')
    print(__file__)
    print(os.path.dirname(__file__))
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


if __name__ == '__main__':
    #generate_ULconstants()
    pass


