import numpy as np
import time
import logging
import sys

import ctypes
from ctypes import byref

from pyqtgraph.Qt import QtCore, QtGui
from pyqtgraph.util.mutex import Mutex

from ..core import Node, register_node_type



if sys.platform.startswith('win'):
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
else:
    HAVE_MC = False

class ULError( Exception ):
    def __init__(self, errno):
        self.errno = errno
        err_msg = ctypes.create_string_buffer(ULConst.ERRSTRLEN)
        errno2 = _cbw.cbGetErrMsg(errno,err_msg)
        assert errno2==0, Exception('_cbw.cbGetErrMsg do not work')
        errstr = 'ULError %d: %s'%(errno,err_msg.value)                
        Exception.__init__(self, errstr)

def decorate_with_error(f):
    def func_with_error(*args):
        errno = f(*args)
        if errno!=ULConst.NOERRORS:
            raise ULError(errno)
        return errno
    return func_with_error

class CBW:
    def __getattr__(self, attr):
        f = getattr(_cbw, attr)
        return decorate_with_error(f)

if HAVE_MC:
    cbw = CBW()    

# some board are limited and do not have scan of digital port
board_not_support_cbDaqInScan = (b'USB-1616FS', b'USB-1208LS', b'USB-1608FS', b'USB-1608FS-Plus')


class MeasurementComputing(Node):
    """Simple wrapper around universal library (cbw) for measurement computing card.
    
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
    
    This Node grab both analog channels and digital when possible.
    Some device (USB-1608FS, USB-1616FS, ..) do not support scan of digital
    port. In that case they are ignored.
    
    
    Parameters for configure
    ----------
    sample_rate : float
        Sample rate for analog input clock.
    ai_channel_index : list of int
        List of analog channel.
    ai_ranges: list of tuples or tuples
        List of range for  analog channels expromed in Volts
        Example ai_ranges = [(-5, 5), (-10, 10)]
        If only one tuple then it is apllied to all channels.
    ai_mode: str or None
        Some card can be configured with an ai mode in ('differential', 'single-ended', 'grounded')
        None by default because not all card can deal with this.
    
    """
    _output_specs = {'aichannels' : dict(streamtype = 'analogsignal'),
                    'dichannels' : dict(streamtype = 'digitalsignal'),
                    }

    def __init__(self, **kargs):
        Node.__init__(self, **kargs)
        assert HAVE_MC, "MeasurementComputing depend on MeasurementComputing DLL"

    def _configure(self, board_num=0, sample_rate=1000., ai_channel_index=None,
                ai_ranges=(-5, 5), ai_mode=None):
        
        self.board_info = self.scan_device_info(board_num)
        
        if ai_channel_index is None:
            ai_channel_index = np.arange(self.board_info['nb_ai_channel'])
        
        self.board_num = int(board_num)
        self.sample_rate = sample_rate
        self.ai_channel_index = ai_channel_index
        
        self.nb_ai_channel = len(ai_channel_index)
        if isinstance(ai_ranges, tuple):
            ai_ranges = [ai_ranges] * self.nb_ai_channel
        self.ai_ranges = ai_ranges
        assert len(self.ai_ranges) == self.nb_ai_channel, 'length error for ai_ranges'
        assert all(ai_range in range_convertion for ai_range in ai_ranges), 'Range not supported {}'.format(ai_ranges)
        
        self.ai_mode = ai_mode
        if ai_mode is not None:
            assert ai_mode in mode_convertion, 'Unknown ai mode. Not in {}'.format(mode_convertion.keys())
        
        self.di_dtype = None
        if self.board_info['nb_di_port']>0:
            bit_by_port = np.array(self.board_info['bit_by_port'])
            
            # some internal limitation
            assert np.all(bit_by_port == bit_by_port[0]), 'Unsupported port with different bits {}'.format(bit_by_port)
            assert bit_by_port[0] in (8, 16), 'Unsupported port with bits {}'.format(bit_by_port)
            
            if bit_by_port[0] == 8:
                self.di_dtype = 'uint8'
            else:
                self.di_dtype = 'uint16'

        
        self.prepare_device()
        
        self.outputs['aichannels'].spec['shape'] = (-1, self.nb_ai_channel)
        self.outputs['aichannels'].spec['dtype'] = 'float32'
        self.outputs['aichannels'].spec['sample_rate'] = self.real_sample_rate
        self.outputs['aichannels'].spec['nb_channel'] = self.nb_ai_channel
        
        if self.board_info['nb_di_port']>0:    
            self.outputs['dichannels'].spec['shape'] = (-1, self.board_info['nb_di_port'])
            self.outputs['dichannels'].spec['dtype'] = self.di_dtype
            self.outputs['dichannels'].spec['sample_rate'] = self.real_sample_rate

    def after_output_configure(self, outputname):
        if outputname == 'aichannels':
            channel_info = [ {'name': 'ai{}'.format(c)} for c in self.ai_channel_index ]
        elif outputname == 'dichannels':
            channel_info = [ {'name': 'di{}'.format(c)} for c in range(self.board_info['nb_di_channel']) ]
        self.outputs[outputname].params['channel_info'] = channel_info

    def _initialize(self):
        self.thread = MeasurementComputingThread(self, parent=None)

    def _start(self):
        self._start_daq_scan()
        #~ try:
            #~ self._start_daq_scan()
        #~ except ULError as e:
            #~ if e.errno == 35:
                #~ #do not known why sometimes just a second try and it is OK
                #~ time.sleep(1.)
                #~ self._start_daq_scan()
            #~ elif e.errno == ULConst.BADBOARDTYPE :
                #~ logging.info(self.board_info['board_name'], 'do not support cbDaqInScan')
                #~ raise()
        #~ self.timer.start()
        self.thread.start()

    def _stop(self):
        self.thread.stop()
        self.thread.wait()
        self._stop_daq_scan()

    def _start_daq_scan(self):
        if self.mode_daq_scan == 'cbAInScan':
            low_chan = int(min(self.ai_channel_index))
            high_chan = int(max(self.ai_channel_index))
            cbw.cbAInScan(self.board_num, low_chan, high_chan, ctypes.c_long(self.raw_arr.size),
                    ctypes.byref(self.real_sr), ctypes.c_int(self.gain_array[0]),
                    ctypes.c_void_p(self.raw_arr.ctypes.data), self.options)
            self.function = ULConst.AIFUNCTION
        elif self.mode_daq_scan == 'cbDaqInScan':
            cbw.cbDaqInScan(self.board_num,  ctypes.c_void_p(self.chan_array.ctypes.data),
                ctypes.c_void_p(self.chan_array_type.ctypes.data),
                ctypes.c_void_p(self.gain_array.ctypes.data),
                self.nb_total_channel, byref(self.real_sr), byref(self.pretrig_count),
                byref(self.total_count), ctypes.c_void_p(self.raw_arr.ctypes.data), self.options)
            self.function = ULConst.DAQIFUNCTION
    
    def _stop_daq_scan(self):
    
        if self.mode_daq_scan == 'cbAInScan':
            cbw.cbStopBackground(ctypes.c_int(self.board_num))
        elif self.mode_daq_scan == 'cbDaqInScan':
            cbw.cbStopBackground(ctypes.c_int(self.board_num), ctypes.c_int(self.function))
    
    def _close(self):
        del self.raw_arr

    def scan_device_info(self, board_num):
        board_info = { }
        
        config_val = ctypes.c_int(0)
        board_name = ctypes.create_string_buffer(ULConst.BOARDNAMELEN)
        cbw.cbGetBoardName(board_num, byref(board_name))
        board_info['board_name'] = board_name.value
        l = [ 
                ('board_type', ULConst.BOARDINFO, ULConst.BIBOARDTYPE),
                ('nb_ai_channel', ULConst.BOARDINFO, ULConst.BINUMADCHANS),
                ('nb_ao_channel', ULConst.BOARDINFO, ULConst.BINUMDACHANS),
                #~ ('BINUMIOPORTS', ULConst.BOARDINFO, ULConst.BINUMIOPORTS),
                ('nb_di_port', ULConst.BOARDINFO, ULConst.BIDINUMDEVS),
                ('serial_num', ULConst.BOARDINFO, ULConst.BISERIALNUM),
                ('factory_id', ULConst.BOARDINFO, ULConst.BIFACTORYID),
                ]
        for key, info_type, config_item in l:
            cbw.cbGetConfig(info_type, board_num, 0, config_item,
                    byref(config_val))
            board_info[key] = config_val.value
        
        # packet size
        if board_info['board_name'] in [b'USB-1208LS']:
            board_info['packet_size'] = 64
        elif board_info['board_name'] in [b'USB-1208FS', b'USB-1408FS', b'USB-7204',  b'USB-1608FS']:
            board_info['packet_size'] = 31
        else:
            board_info['packet_size'] = 1
        
        if board_info['board_name'] in board_not_support_cbDaqInScan:
            # can not do cbAInScan and so no digital port
            board_info['nb_di_port'] = 0 
            
        board_info['list_di_port'] = []
        board_info['bit_by_port'] = []
        if board_info['nb_di_port']>0:
            for num_dev in range(board_info['nb_di_port']):
                cbw.cbGetConfig(ULConst.DIGITALINFO, board_num, num_dev,
                                        ULConst.DIDEVTYPE, byref(config_val))
                didevtype = config_val.value
                cbw.cbGetConfig(ULConst.DIGITALINFO, board_num, num_dev,
                                        ULConst.DINUMBITS, byref(config_val))
                nbits = config_val.value
                if didevtype==ULConst.AUXPORT:
                    # This port is not stremable
                    board_info['nb_di_port'] -= 1
                else:
                    board_info['bit_by_port'].append(nbits)
                    board_info['list_di_port'].append(didevtype)
                
        board_info['nb_di_channel'] = sum(board_info['bit_by_port'])
        
        return board_info
    
    def prepare_device(self):

        if self.ai_mode is not None:
            cbw.cbAInputMode(ctypes.c_int(self.board_num), ctypes.c_int(mode_convertion[self.ai_mode]))
            #~ for c in self.ai_channel_index:
                #~ cbw.cbAChanInputMode(ctypes.c_int(self.board_num), ctypes.c_int(c),
                                    #~ ctypes.c_int(mode_convertion[self.ai_mode]))

        
        #digital input
        self.nb_total_channel = self.nb_ai_channel + self.board_info['nb_di_port']
        
        self.chan_array = np.array(self.ai_channel_index +\
                    self.board_info['list_di_port'], dtype = 'uint16')
        
        array_types = [ULConst.ANALOG] * self.nb_ai_channel
        if self.di_dtype == 'uint8':
            array_types += [ULConst.DIGITAL8] * self.board_info['nb_di_port']
        elif self.di_dtype == 'uint16':
            array_types += [ULConst.DIGITAL16] * self.board_info['nb_di_port']
        self.chan_array_type = np.array(array_types, dtype='int16')
        
        # this is for cbDaqInScan
        self.gain_array = np.array([ range_convertion[ai_range] for ai_range in self.ai_ranges] +\
                    [0] * self.board_info['nb_di_port'], dtype = np.int16)
        self.real_sr = ctypes.c_long(int(self.sample_rate))
        
        # prepare gain/ offset by analog channel
        self.channel_gains = np.zeros(self.nb_ai_channel, dtype='float32')
        self.channel_offsets = np.zeros(self.nb_ai_channel, dtype='float32')
        for c, chan in enumerate(self.ai_channel_index):
            ai_range =  self.ai_ranges[c]
            self.channel_gains[c] = (ai_range[1] - ai_range[0]) / 2**16
            if ai_range[0]==-ai_range[1]:
                self.channel_offsets[c]= -self.channel_gains[c]*2**15
        self.channel_gains = self.channel_gains.reshape(1,-1)
        self.channel_offsets = self.channel_offsets.reshape(1,-1)
        
        # buffer of 10S rounded to packetsize
        self.internal_size = int(10.*self.sample_rate)
        self.internal_size = self.internal_size - self.internal_size%(self.board_info['packet_size'])

        self.raw_arr = np.zeros((self.internal_size, self.nb_total_channel), dtype='uint16')
        self.pretrig_count = ctypes.c_long(0)
        self.total_count = ctypes.c_long(int(self.raw_arr.size))
        self.options = ctypes.c_int(ULConst.BACKGROUND  + ULConst.CONTINUOUS + ULConst.CONVERTDATA)
        
        if self.board_info['board_name'] in board_not_support_cbDaqInScan:
            #for some old card the scanning mode is limited
            self.mode_daq_scan = 'cbAInScan'
            assert np.all(np.diff(self.ai_channel_index) == 1), 'For this card you must select continuous cannel indexes'
            assert self.board_info['nb_di_port'] ==0, 'You can not sample digital ports'
            assert np.all(self.gain_array[0]==self.gain_array), 'For this card gain must be identical'
        else:
            self.mode_daq_scan = 'cbDaqInScan'

        # get the real sample_rate here :  a start/stop and read self.real_sr
        self._start_daq_scan()
        self._stop_daq_scan()
        self.real_sample_rate = float(self.real_sr.value)

        self.ai_mask = np.zeros(self.nb_total_channel, dtype = bool)
        self.ai_mask[:self.nb_ai_channel] = True
        self.di_mask = ~self.ai_mask
    

register_node_type(MeasurementComputing)


class MeasurementComputingThread(QtCore.QThread):
    """
    MeasurementComputing thread that grab continuous data.
    """
    def __init__(self, node, parent=None):
        QtCore.QThread.__init__(self, parent=parent)
        
        self.node = node

        self.lock = Mutex()
        self.running = False
        
    def run(self):
        
        board_num = self.node.board_num
        function= self.node.function
        nb_total_channel = self.node.nb_total_channel
        internal_size = self.node.internal_size
        outputs = self.node.outputs
        raw_arr = self.node.raw_arr
        ai_mask = self.node.ai_mask
        di_mask = self.node.di_mask
        board_info = self.node.board_info
        di_dtype = self.node.di_dtype
        channel_gains = self.node.channel_gains
        channel_offsets = self.node.channel_offsets
        
        status = ctypes.c_int(0)
        cur_count = ctypes.c_long(0)
        cur_index = ctypes.c_long(0)
        
        
        last_index = 0
        head = 0
        
        with self.lock:
            self.running = True
        
        while True:
            with self.lock:
                if not self.running:
                    break
            
            cbw.cbGetIOStatus( ctypes.c_int(board_num), byref(status),
                byref(cur_count), byref(cur_index), ctypes.c_int(function))
            
            if cur_index.value==-1: 
                continue
            
            index = cur_index.value // nb_total_channel
            #~ print('index', index)
            
            if index == last_index :
                time.sleep(.01)
                continue
            
            
            if index<last_index:
                #end of internal ring buffer
                new_samp = internal_size - last_index
                head += new_samp
                ai_arr = raw_arr[last_index:, ai_mask].astype('float32')
                ai_arr *= channel_gains
                ai_arr += channel_offsets
                outputs['aichannels'].send(ai_arr, index=head)
                
                if board_info['nb_di_port']>0:
                    outputs['dichannels'].send(raw_arr[last_index:, di_mask].astype(di_dtype), index=head)
                
                last_index = 0
                
            new_samp = index - last_index
            head += new_samp
            ai_arr = raw_arr[last_index:index, ai_mask].astype('float32')
            ai_arr *= channel_gains
            ai_arr += channel_offsets
            outputs['aichannels'].send(ai_arr, index=head)
            
            if board_info['nb_di_port']>0:
                outputs['dichannels'].send(raw_arr[last_index:index, di_mask].astype(di_dtype), index=head)
            
            last_index = index%internal_size
            
            # be nice
            time.sleep(.01)
            

    def stop(self):
        with self.lock:
            self.running = False


class ULConst:
    ERRSTRLEN    =    256    
    NOERRORS    =    0

    AIFUNCTION    =    1    # Analog Input Function
    DAQIFUNCTION    =    6    # Daq Input Function       
    BOARDNAMELEN    =    25    

    BOARDINFO    =    2    
    
    BINUMDACHANS    =    13    # Number of D/A channels 

    BIBOARDTYPE    =    1    # Board Type (0x101 - 0x7FFF) 
    BINUMADCHANS    =    7    # Number of A/D channels 
    BINUMIOPORTS    =    15    # I/O address space used by board 
    BIDINUMDEVS    =    9    # Number of digital devices 
    BISERIALNUM    =    214    # Serial Number for USB boards 
    BIFACTORYID    =    272    

    DIGITALINFO    =    3    

    DIDEVTYPE    =    2    # AUXPORT or xPORTA - CH 

    DINUMBITS    =    6    # Number of bits in port 

    AUXPORT    =    1    

    ANALOG    =    0    
    DIGITAL8    =    1    
    DIGITAL16    =    2


    BACKGROUND    =    0x0001    # Run in background, return immediately 

    CONTINUOUS    =    0x0002    # Run continuously until cbstop() called 

    NOCONVERTDATA    =    0x0000    # Return raw data 
    CONVERTDATA    =    0x0008    # Return converted A/D data 

    DIFFERENTIAL = 0
    SINGLE_ENDED = 1
    GROUNDED = 16    

    BIP60VOLTS    =    20    # -60 to 60 Volts 
    BIP30VOLTS    =    23    
    BIP20VOLTS    =    15    # -20 to +20 Volts 
    BIP15VOLTS    =    21    # -15 to +15 Volts 
    BIP10VOLTS    =    1    # -10 to +10 Volts 
    BIP5VOLTS    =    0    # -5 to +5 Volts 
    BIP4VOLTS    =    16    # -4 to + 4 Volts 
    BIP2PT5VOLTS    =    2    # -2.5 to +2.5 Volts 
    BIP2VOLTS    =    14    # -2.0 to +2.0 Volts 
    BIP1PT25VOLTS    =    3    # -1.25 to +1.25 Volts 
    BIP1VOLTS    =    4    # -1 to +1 Volts 
    BIPPT625VOLTS    =    5    # -.625 to +.625 Volts 
    BIPPT5VOLTS    =    6    # -.5 to +.5 Volts 
    BIPPT25VOLTS    =    12    # -0.25 to +0.25 Volts 
    BIPPT2VOLTS    =    13    # -0.2 to +0.2 Volts 
    BIPPT1VOLTS    =    7    # -.1 to +.1 Volts 
    BIPPT05VOLTS    =    8    # -.05 to +.05 Volts 
    BIPPT01VOLTS    =    9    # -.01 to +.01 Volts 
    BIPPT005VOLTS    =    10    # -.005 to +.005 Volts 
    BIP1PT67VOLTS    =    11    # -1.67 to +1.67 Volts 
    BIPPT312VOLTS    =    17    # -0.312 to +0.312 Volts 
    BIPPT156VOLTS    =    18    # -0.156 to +0.156 Volts 
    BIPPT125VOLTS    =    22    # -0.125 to +0.125 Volts 
    BIPPT078VOLTS    =    19    # -0.078 to +0.078 Volts 
    UNI10VOLTS    =    100    
    UNI5VOLTS    =    101    # 0 to 5 Volts 
    UNI4VOLTS    =    114    # 0 to 4 Volts 
    UNI2PT5VOLTS    =    102    # 0 to 2.5 Volts 
    UNI2VOLTS    =    103    # 0 to 2 Volts 
    UNI1PT67VOLTS    =    109    # 0 to 1.67 Volts 
    UNI1PT25VOLTS    =    104    # 0 to 1.25 Volts 
    UNI1VOLTS    =    105    # 0 to 1 Volt 
    UNIPT5VOLTS    =    110    # 0 to .5 Volt 
    UNIPT25VOLTS    =    111    # 0 to 0.25 Volt 
    UNIPT2VOLTS    =    112    # 0 to .2 Volt 
    UNIPT1VOLTS    =    106    # 0 to .1 Volt 
    UNIPT05VOLTS    =    113    # 0 to .05 Volt 
    UNIPT02VOLTS    =    108    
    UNIPT01VOLTS    =    107

    

range_convertion = {
    (-10, 10) : ULConst.BIP10VOLTS,
    (-5, 5) : ULConst.BIP5VOLTS,
    (-1, 1) : ULConst.BIP1VOLTS,
    (-0.1, 0.1) : ULConst.BIPPT1VOLTS,
}

mode_convertion = {
    'differential' : ULConst.DIFFERENTIAL,
    'single-ended' : ULConst.SINGLE_ENDED,
    'grounded' : ULConst.GROUNDED,
}
