import numpy as np
import logging
import ctypes
import os
import time

from ..core import Node, register_node_type, ThreadPollInput
from pyqtgraph.Qt import QtCore, QtGui
from pyqtgraph.util.mutex import Mutex


# http://www.ifnamemain.com/posts/2013/Dec/10/c_structs_python/
# http://scipy-cookbook.readthedocs.io/items/Ctypes.html
# https://stackoverflow.com/questions/2804893/c-dll-export-decorated-mangled-names


"""
Question for blackrock support:
   * possible to get interleave channels ?
   * chunksize (latency) ?
   * channel selection
   * chan_info.smpgroup  ??



TODO:
  * apply_config = check channel number
  * connection choice (UDP, central)
  * debug UDP only
  * argtypes to be safe on C call
    
"""






class Blackrock(Node):
    """
    Node on top the cbSdk.dll
    This grab only the continuous signal for the moment of aichannels.
    Spike/event are not streamed here.
    But to come soon.
    
    Connection are done with UDP directly on the NSP so several instance
    of this Node can run on the same or sevral PCs.
    """
    
    _output_specs = {
        'aichannels': {}
    }
    
    def __init__(self, dll_path=None, version='6.5.4', **kargs):
        Node.__init__(self, **kargs)
        self.cbSdk = open_sbSdk_dll(dll_path=dll_path, version=version)
        assert self.cbSdk is not None, "Imposible to found DLL: cbsdkx64.dll"

    def _configure(self, nInstance=0, connection_type='udp',
            nInPort=51002, nOutPort=51001, nRecBufSize=4096*2048,
            szInIP=b"192.168.137.1", szOutIP=b"192.168.137.128",
            ai_channels=[], apply_config=False):
        """
        The following variable come from the blacrock dialect
        nInstance
        connection_type 'udp' or 'central' or 'default'
        nInPort
        nOutPort
        nRecBufSize
        szInIP
        szOutIP
        
        ai_channels are blackrock channel 1-based
        
        apply_config: True/False if True it apply config to ai_channels.
                    False use NSP config done by user with "Central" software.
        
        """
        # the following variable come from the blacrock dialect
        self.nInstance = nInstance
        self.connection_type = connection_type
        self.nInPort = nInPort
        self.nOutPort = nOutPort
        self.nRecBufSize = nRecBufSize
        self.szInIP = szInIP
        self.szOutIP = szOutIP
        
        # here it is my own
        self.ai_channels = ai_channels
        self.nb_channel = len(self.ai_channels)
        self.apply_config = apply_config
        
        
        self.outputs['aichannels'].spec.update({
            'chunksize': 300, # TODO check this
            #~ 'shape': (chunksize, self.nb_channel),
            'shape': (-1, self.nb_channel),
            'dtype': 'int16',
            'sample_rate': 30000.,
            'nb_channel': self.nb_channel,
        })
        
    
    def _initialize(self):
        cbSdk = self.cbSdk
        
        con = cbSdkConnection(self.nInPort, self.nOutPort,self.nRecBufSize, 0,
                        self.szInIP, self.szOutIP)
        # print(ctypes.sizeof(con)) this should be 28 when read .h but in factc it is 32
        conv = { 'default':0, 'central':1, 'udp': 2}
        con_type = ctypes.c_int32(conv.get(self.connection_type, 0))
        cbSdk.Open(ctypes.c_uint32(self.nInstance),con_type, con)

        
        self.nb_available_ai_channel = None
        self._all_channel_names = []
        for c in range(cbSdk.cbNUM_ANALOG_CHANS):
            chan_info = cbPKT_CHANINFO()
            try:
                cbSdk.GetChannelConfig(self.nInstance, ctypes.c_short(c+1), ctypes.byref(chan_info))
                #~ print('c', c, 'chan', chan_info.chan, 'chid',chan_info.chid, chan_info.proc, chan_info.bank, 
                            #~ chan_info.label, 'type', chan_info.type,
                            #~ 'ainpopts', chan_info.ainpopts, 'smpgroup', chan_info.smpgroup,
                            #~ 'ainpcaps', chan_info.ainpcaps)
                self._all_channel_names.append(str(chan_info.chan))
            except:
                self.nb_available_ai_channel = c
                break

        
        self.channel_names = [ self._all_channel_names[ai_chan-1] for ai_chan in self.ai_channels ]
        channel_info = [ {'name': name} for name in range(self.channel_names) ]
        self.outputs['aichannels'].params['channel_info'] = channel_info

        
        #~ print('nb_available_ai_channel', self.nb_available_ai_channel)
        #~ exit()

        if self.apply_config:
            # TODO debug this : this do not work in all situation ?!?
            # configure channels
            for ai_channel in self.ai_channels:
                chan_info = cbPKT_CHANINFO()
                cbSdk.GetChannelConfig(self.nInstance, ctypes.c_short(ai_channel), ctypes.byref(chan_info))
                chan_info.smpfilter = 0 # no filter
                chan_info.smpgroup = 5 # continuous sampling rate (30kHz)
                chan_info.type = 78
                #~ chan_info.ainpopts = 320
                #~ #cbAINP_RAWSTREAM           0x00000040
                #~ chan_info.ainpopts = 0x00000040
                #~ chan_info.smpgroup = 0 # continuous sampling rate (30kHz)
                #~ chan_info.type = 74
                #~ chan_info.ainpopts = 256
                #~ chan_info.ainpopts = 0x00000040 
                chan_info.ainpopts = 256
                
                cbSdk.SetChannelConfig(self.nInstance, ctypes.c_short(ai_channel), ctypes.byref(chan_info))

#define  cbAINP_LNC_OFF             0x00000000      // Line Noise Cancellation disabled
#define  cbAINP_LNC_RUN_HARD        0x00000001      // Hardware-based LNC running and adapting according to the adaptation const
#define  cbAINP_LNC_RUN_SOFT        0x00000002      // Software-based LNC running and adapting according to the adaptation const
#define  cbAINP_LNC_HOLD            0x00000004      // LNC running, but not adapting
#define  cbAINP_LNC_MASK            0x00000007      // Mask for LNC Flags
#define  cbAINP_REFELEC_LFPSPK      0x00000010      // Apply reference electrode to LFP & Spike
#define  cbAINP_REFELEC_SPK         0x00000020      // Apply reference electrode to Spikes only
#define  cbAINP_REFELEC_MASK        0x00000030      // Mask for Reference Electrode flags
#define  cbAINP_RAWSTREAM_ENABLED   0x00000040      // Raw data stream enabled
#define  cbAINP_OFFSET_CORRECT      0x00000100      // Offset correction mode (0-disabled 1-enabled)
        
        
        #~ CBSDKAPI    cbSdkResult cbSdkSetTrialConfig(UINT32 self.nInstance,
                         #~ UINT32 bActive, UINT16 begchan = 0, UINT32 begmask = 0, UINT32 begval = 0,
                         #~ UINT16 endchan = 0, UINT32 endmask = 0, UINT32 endval = 0, bool bDouble = false,
                         #~ UINT32 uWaveforms = 0, UINT32 uConts = cbSdk_CONTINUOUS_DATA_SAMPLES, UINT32 uEvents = cbSdk_EVENT_DATA_SAMPLES,
                         #~ UINT32 uComments = 0, UINT32 uTrackings = 0, bool bAbsolute = false); // Configure a data collection trial
        cbSdk.SetTrialConfig(self.nInstance, 1, 0, 0, 0, 0, 0, 0, False, 0, cbSdk.cbSdk_CONTINUOUS_DATA_SAMPLES, 0, 0, 0, True)
        
        # create structure to hold the data
        # here contrary to example in CPP I create only one big continuous buffer
        # that will be sliced in continuous arrays with numpy
        
        self.trialcont = cbSdk.cbSdkTrialCont()
        self.ai_buffer = np.zeros((cbSdk.cbNUM_ANALOG_CHANS, cbSdk.cbSdk_CONTINUOUS_DATA_SAMPLES, ), dtype='int16')
        
        for i in range(cbSdk.cbNUM_ANALOG_CHANS):
            arr = self.ai_buffer[i,: ]
            # self.trial.samples[i] = ctypes.cast(np.ctypeslib.as_ctypes(arr), ctypes.c_void_p)
            #~ print(arr.flags)
            
            addr, read_only_flag  = arr.__array_interface__['data']
            self.trialcont.samples[i] = ctypes.c_void_p(addr)
            
        self.thread = BlackrockThread(self, parent=None)

    def _start(self):
        self.thread.start()

    def _stop(self):
        self.thread.stop()
        self.thread.wait()

    def _close(self):
        cbSdk.Close(self.nInstance)

class BlackrockThread(QtCore.QThread):
    def __init__(self, node, parent=None):
        QtCore.QThread.__init__(self, parent=parent)
        self.node = node

        self.lock = Mutex()
        self.running = False
        
    def run(self):
        with self.lock:
            self.running = True
        
        stream = self.node.outputs['aichannels']
        trialcont = self.node.trialcont
        ai_buffer = self.node.ai_buffer
        nInstance = self.node.nInstance
        nb_channel = self.node.nb_channel
        cbSdk = self.node.cbSdk
        
        n = 0
        next_timestamp = None
        t0 = time.perf_counter()
        while True:
            #~ print('n', n)
            with self.lock:
                if not self.running:
                    break
            
            cbSdk.InitTrialData(nInstance, 1, None, ctypes.byref(trialcont), None, None)
            #~ print('INIT trialcont.count', trialcont.count)
            #~ CBSDKAPI    cbSdkResult cbSdkGetTrialData(UINT32 nInstance,
                                          #~ UINT32 bActive, cbSdkTrialEvent * trialevent, cbSdkTrialCont * trialcont,
                                          #~ cbSdkTrialComment * trialcomment, cbSdkTrialTracking * trialtracking);            
            
            #~ print(' trialcont.count',  trialcont.count)
            
            if trialcont.count==0:
                time.sleep(0.003)
                continue
            
            #~ cbSdk.GetTrialData(nInstance, 1, None, ctypes.byref(trialcont), None, None)
            
            num_samples = np.ctypeslib.as_array(trialcont.num_samples)[:nb_channel]
            
            #~ print(num_samples)
            
            if num_samples[0] < 300:
                # it is too early!!!!!!
                print('too early (<300)', num_samples[0])
                print('*'*5)
                time.sleep(0.003)
                continue
            
            #~ print(num_samples)
            
            cbSdk.GetTrialData(nInstance, 1, None, ctypes.byref(trialcont), None, None)
            #~ print(trialcont)
            #~ print('yep')
            #~ if trialcont.count==0:
                #~ continue
            print('trialcont.count', trialcont.count, 'trialcont.time', trialcont.time, 'trialcont.num_samples', trialcont.num_samples[0])
            #~ if trialcont.count==0:
                #~ time.sleep(0.001)
                #~ continue
            t1 = time.perf_counter()
            print((t1-t0)*1000)
            t0 = t1
            
            num_samples = np.ctypeslib.as_array(trialcont.num_samples)[:nb_channel]
            #~ print(num_samples)
            #~ assert np.all(num_samples[0]==num_samples)
            
            num_sample = num_samples[0]
            #~ print('num_sample', num_sample)
            #~ print(ai_buffer.shape)
            
            #~ print(np.ctypeslib.as_array(trialcont.num_samples)[:10])
            #~ print(np.ctypeslib.as_array(trialcont.sample_rates)[:10])
            #~ print(np.ctypeslib.as_array(trialcont.chan)[:10])
            #~ print(ai_buffer[0:10, :20])
            
            
            # since internanlly the memory layout is chanXsample we swap it
            #~ data = ai_buffer.T.copy()
            #~ data = ai_buffer[:, :trialcont.num_samples[0]].T.astype('float32')
            #~ data = ai_buffer[:nb_channel, : trialcont.num_samples[0]].T.copy()
            data = ai_buffer[:nb_channel, : num_sample].T.copy()
            #~ data = ai_buffer[:nb_channel, :300].T.copy()
            #~ data = ai_buffer[: trialcont.num_samples[0], 0].reshape(-1, 1)
            print('data.shape', data.shape)
            #~ print('data.sum', np.sum(data))
            n += data.shape[0]
            stream.send(data, index=n)
            
            if next_timestamp is not None:
                print(next_timestamp, trialcont.time, next_timestamp==trialcont.time)
                pass
            next_timestamp = trialcont.time + num_sample
            
            print('*'*5)
            #~ cbSdk.InitTrialData(nInstance, 1, None, ctypes.byref(trialcont), None, None)
            time.sleep(0)

    def stop(self):
        with self.lock:
            self.running = False



register_node_type(Blackrock)


class CbSdkError(Exception):
    """
    This handle properly exception woth error message.
    """
    def __init__(self, errno, func_name=''):
        self.errno = errno
        self.func_name = func_name
        err_msg = error_message_dict.get(errno, 'Unkown Error message')
        errstr = 'CbSdkError %d: %s %s'%(errno, self.func_name, err_msg)                
        Exception.__init__(self, errstr)


def open_sbSdk_dll(dll_path=None, version='6.5.4'):
    """
    Try to open cbsdkx64.dll.
    This DLL is C++ and not C compliant. So standard ctypes call do
    not work because function names are mangled.
    
    With http://www.dependencywalker.com/ we can inspect the DLL and 
    call func by index.
    
    So actual implementation only support some version: 7.0.3, 6.05.04 and 6.04
    To support more version we need to "dependencywalker" again
    
    Path are searched in:
      * C:/Program Files (x86)/Blackrock Microsystems/Cerebus Windows Suite
      * or C:/Program Files (x86)/Blackrock Microsystems/NeuroPort Windows Suite
    
    This function do not retun the ctypes DLL itself but a mapper
    that do the same with correct error message.
    
    Usage:
    cbSdk = open_sbSdk_dll()
    cbSdk.Open(...)
    cbSdk.Close(...)
    
    """
    if dll_path is None:
        dll_path = 'C:/Program Files (x86)/Blackrock Microsystems/NeuroPort Windows Suite'
        if not os.path.exists(dll_path):
            dll_path = 'C:/Program Files (x86)/Blackrock Microsystems/Cerebus Windows Suite'
    if not os.path.exists(dll_path):
        return None
    p1, p2 = dll_path, dll_path + '/cbsdk/lib'
    os.environ['PATH'] = p1 + ';' + p2 + ';' + os.environ['PATH']

    
    try:
        dll_cbsdk = ctypes.windll.LoadLibrary('cbsdkx64.dll')
    except :
        return None

    
    def decorate_with_error(f, func_name):
        #~ print('decorate_with_error', f, func_name)
        def func_with_error(*args):
            #~ print('DLL function call', func_name, args)
            errno = f(*args)
            # CBSDKRESULT_SUCCESS = 0
            if errno != 0:
                raise CbSdkError(errno, func_name)
            return errno
        return func_with_error
    
    func_name_to_func_index = {
        '6.5.4': {
            'Open' : 23,
            'Close' : 3,
            'GetChannelConfig' : 5,
            'SetChannelConfig' : 28,
            'SetTrialConfig' : 38,
            'InitTrialData' : 21,
            'GetTrialData' : 17,
        },
        '6.4': {
            'Open' : 21,
            'Close' : 3,
            'GetChannelConfig' : 5,
            'SetChannelConfig' : 26,
            'SetTrialConfig' : 36,
            'InitTrialData' : 19,
            'GetTrialData' : 15,
        }
    }
    func_name_to_func_index['7.0.3'] = func_name_to_func_index['6.5.4']
    
    if version not in func_name_to_func_index:
        return None
    
    class CBSDK_mapper:
        def __init__(self, version):
            for name, ind in func_name_to_func_index[version].items():
                func = dll_cbsdk[ind]
                # TODO argtypes for some functions here
                func_decorated = decorate_with_error(func, name)
                setattr(self, name, func_decorated)
            
            if version in ('7.0.3', ):
                self.cbNUM_ANALOG_CHANS = 256 + 16
            elif version in ('6.5.4', '6.4'):
                self.cbNUM_ANALOG_CHANS = 128 + 16
            
            self.cbSdk_CONTINUOUS_DATA_SAMPLES = 102400


            class cbSdkTrialCont_(ctypes.Structure):
                _fields_ = [
                    ('count', UINT16), # Number of valid channels in this trial (up to cbNUM_ANALOG_CHANS)
                    ('chan', (UINT16 * self.cbNUM_ANALOG_CHANS)), # Channel numbers (1-based)
                    ('sample_rates', (UINT16 * self.cbNUM_ANALOG_CHANS)), # Current sample rate (samples per second)
                    ('num_samples', (UINT32 * self.cbNUM_ANALOG_CHANS)), # Number of samples
                    ('time', UINT32), # Start time for trial continuous data
                    ('samples', (ctypes.c_void_p * self.cbNUM_ANALOG_CHANS)), # Buffer to hold sample vectors
                ]
            self.cbSdkTrialCont = cbSdkTrialCont_

    
    cbSdk = CBSDK_mapper(version)
    
    return cbSdk

# constant and Struct

# TODO do this dynamicaly in open_dll

#~ #cbNUM_ANALOG_CHANS = 256 + 16 # this is version 7.0.x
#~ cbNUM_ANALOG_CHANS = 128 + 16 # this is version 6.5.4
#~ cbSdk_CONTINUOUS_DATA_SAMPLES = 102400

#~ CBSDKCONNECTION_DEFAULT = 0 # Try Central then UDP
#~ CBSDKCONNECTION_CENTRAL = 1 # Use Central
#~ CBSDKCONNECTION_UDP = 2 # Use UDP
#~ CBSDKCONNECTION_CLOSED = 3 # Closed
#~ CBSDKCONNECTION_COUNT = 4 # Allways the last value (Unknown)



# for convinient translation
INT32 = ctypes.c_int32
UINT32 = ctypes.c_uint32
INT16 = ctypes.c_int16
UINT16 = ctypes.c_uint16
INT8 = ctypes.c_int8
UINT8 = ctypes.c_uint8
CHAR = ctypes.c_char



class cbSdkConnection(ctypes.Structure):
    _pack_ = 1
    _fields_ = [
        
        ('nInPort', INT32), # int Client port number
        ('nOutPort', INT32), # int Instrument port number
        ('nRecBufSize', INT32), # int Receive buffer size (0 to ignore altogether)
        ('bad', INT32), # bad
        ('szInIP', ctypes.c_char_p), # Client IPv4 address
        ('szOutIP', ctypes.c_char_p), # Instrument IPv4 address
        
    ]
    
    #~ def __init__(self, nInPort=51002,
                       #~ nOutPort=51001,
                       #~ nRecBufSize=4096*2048,
                       #~ szInIP=b"192.168.137.1",
                       #~ szOutIP=b"192.168.137.128"):
        #~ self._szInIP = ctypes.c_char_p(szInIP)
        #~ self._szOutIP = ctypes.c_char_p(szOutIP)
        #~ super().__init__(nInPort, nOutPort, nRecBufSize,
                    #~ szInIP,
                    #~ szOutIP)
                    #~ self._szInIP,
                    #~ self._szOutIP)
                    #~ ctypes.c_char_p(szInIP),
                    #~ ctypes.c_char_p(szOutIP))
        
                    #~ ctypes.byref(ctypes.create_string_buffer(szInIP)),
                    #~ ctypes.byref(ctypes.create_string_buffer(szOutIP)))



class cbSCALING(ctypes.Structure):
    _pack_ = 1
    _fields_ = [
        ('digmin', INT16),
        ('digmax', INT16),
        ('anamin', INT32),
        ('anamax', INT32),
        ('anagain', INT32),
        ('anaunit', CHAR*8),
    ]

class cbFILTDESC(ctypes.Structure):
    _pack_ = 1
    _fields_ = [
        ('label', CHAR*16), 
        ('hpfreq', UINT32), # high-pass corner frequency in milliHertz
        ('hporder', UINT32), # high-pass filter order
        ('hptype', UINT32), # high-pass filter type
        ('lpfreq', UINT32), # low-pass frequency in milliHertz
        ('lporder', UINT32),# low-pass filter order
        ('lptype', UINT32), # low-pass filter type
    ]

class cbMANUALUNITMAPPING(ctypes.Structure):
    _pack_ = 1
    _fields_ = [
        ('nOverride', INT16),
        ('afOrigin', INT16*3),
        ('afShape', (INT16*3)*3),
        ('aPhi', INT16),
        ('bValid', UINT32),
    ]

class cbHOOP(ctypes.Structure):
    _pack_ = 1
    _fields_ = [
        ('valid', UINT16),
        ('time', INT16),
        ('min', INT16),
        ('max', INT16),
    ]


class cbPKT_CHANINFO(ctypes.Structure):
    _pack_ = 1
    _fields_ = [
        ('time', UINT32), # system clock timestamp
        ('chid', UINT16), # 0x8000
        ('type', UINT8), # cbPKTTYPE_AINP*
        ('dlen', UINT8), # cbPKT_DLENCHANINFO
        
        ('chan', UINT32), # actual channel id of the channel being configured
        ('proc', UINT32), # the address of the processor on which the channel resides
        ('bank', UINT32), # the address of the bank on which the channel resides
        ('term', UINT32), # the terminal number of the channel within it's bank
        ('chancaps', UINT32), # general channel capablities (given by cbCHAN_* flags)
        ('doutcaps', UINT32), # digital output capablities (composed of cbDOUT_* flags)
        ('dinpcaps', UINT32), # digital input capablities (composed of cbDINP_* flags)
        ('aoutcaps', UINT32), # analog output capablities (composed of cbAOUT_* flags)
        ('ainpcaps', UINT32), # analog input capablities (composed of cbAINP_* flags)
        ('spkcaps', UINT32), # spike processing capabilities
        ('physcalin', cbSCALING), # physical channel scaling information
        ('phyfiltin', cbFILTDESC), # physical channel filter definition
        ('physcalout', cbSCALING), # physical channel scaling information
        ('phyfiltout', cbFILTDESC), # physical channel filter definition
        ('label', CHAR * 16), # Label of the channel (null terminated if <16 characters)
        ('userflags', UINT32), # User flags for the channel state
        ('position', INT32 * 4), # reserved for future position information
        ('scalin', cbSCALING), # user-defined scaling information for AINP
        ('scalout', cbSCALING), # user-defined scaling information for AOUT
        ('doutopts', UINT32), # digital output options (composed of cbDOUT_* flags)
        ('dinpopts', UINT32), # digital input options (composed of cbDINP_* flags)
        ('aoutopts', UINT32), # analog output options
        ('eopchar', UINT32), # digital input capablities (given by cbDINP_* flags)
        
        # here is in fact a union
        ##('monsource', UINT32), # address of channel to monitor
        ## ('outvalue', INT32), # address of channel to monitor
        ('lowsamples', UINT16), # address of channel to monitor
        ('highsamples', UINT16), # 
        ('offset', INT32), # output value
        
        ('trigtype', UINT8), # trigger type (see cbDOUT_TRIGGER_*)
        ('trigchan', UINT16), # trigger channel
        ('trigval', UINT16), # trigger value
        ('ainpopts', UINT32), # analog input options (composed of cbAINP* flags)
        ('lncrate', UINT32), # line noise cancellation filter adaptation rate
        ('smpfilter', UINT32), # continuous-time pathway filter id
        ('smpgroup', UINT32), # continuous-time pathway sample group
        ('smpdispmin', INT32), # continuous-time pathway display factor
        ('smpdispmax', INT32), # continuous-time pathway display factor
        ('spkfilter', UINT32), # spike pathway filter id
        ('spkdispmax', INT32), # spike pathway display factor
        ('lncdispmax', INT32), # Line Noise pathway display factor
        ('spkopts', UINT32), # spike processing options
        ('spkthrlevel', INT32), # spike threshold level
        ('spkthrlimit', INT32), # 
        ('spkgroup', UINT32), # NTrodeGroup this electrode belongs to - 0 is single unit, non-0 indicates a multi-trode grouping
        ('amplrejpos', INT16), # Amplitude rejection positive value
        ('amplrejneg', INT16), # Amplitude rejection negative value
        ('refelecchan', UINT32), # Software reference electrode channel
        ('unitmapping', cbMANUALUNITMAPPING * 5), # manual unit mapping
        ('spkhoops', (cbHOOP * 4) * 5), # spike hoop sorting set  
    ]

#~ print(ctypes.sizeof(cbPKT_CHANINFO))
#~ exit()

#~ class cbSdkTrialCont(ctypes.Structure):
    #~ _fields_ = [
        #~ ('count', UINT16), # Number of valid channels in this trial (up to cbNUM_ANALOG_CHANS)
        #~ ('chan', (UINT16 * cbNUM_ANALOG_CHANS)), # Channel numbers (1-based)
        #~ ('sample_rates', (UINT16 * cbNUM_ANALOG_CHANS)), # Current sample rate (samples per second)
        #~ ('num_samples', (UINT32 * cbNUM_ANALOG_CHANS)), # Number of samples
        #~ ('time', UINT32), # Start time for trial continuous data
        #~ ('samples', (ctypes.c_void_p * cbNUM_ANALOG_CHANS)), # Buffer to hold sample vectors
    #~ ]

# copied from _cbSdkResult
error_message_dict = {
    3: 'If file conversion is needed',
    2: 'Library is already closed',
    1: 'Library is already opened',
    # 0: 'Successful operation',
    -1: 'Not implemented',
    -2: 'Unknown error',
    -3: 'Invalid parameter',
    -4: 'Interface is closed cannot do this operation',
    -5: 'Interface is open cannot do this operation',
    -6: 'Null pointer',
    -7: 'Unable to open Central interface',
    -8: 'Unable to open UDP interface (might happen if default)',
    -9: 'Unable to open UDP port',
    -10: 'Unable to allocate RAM for trial cache data',
    -11: 'Unable to open UDP timer thread',
    -12: 'Unable to open Central communication thread',
    -13: 'Invalid channel number',
    -14: 'Comment too long or invalid',
    -15: 'Filename too long or invalid',
    -16: 'Invalid callback type',
    -17: 'Callback register/unregister failed',
    -18: 'Trying to run an unconfigured method',
    -19: 'Invalid trackable id, or trackable not present',
    -20: 'Invalid video source id, or video source not present',
    -21: 'Cannot open file',
    -22: 'Wrong file format',
    -23: 'Socket option error (possibly permission issue)',
    -24: 'Socket memory assignment error',
    -25: 'Invalid range or instrument address',
    -26: 'library memory allocation error',
    -27: 'Library initialization error',
    -28: 'Conection timeout error',
    -29: 'Resource is busy',
    -30: 'Instrument is offline',
}
