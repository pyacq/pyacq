import numpy as np
import logging
import ctypes
import os

from ..core import Node, register_node_type, ThreadPollInput
from pyqtgraph.Qt import QtCore, QtGui
from pyqtgraph.util.mutex import Mutex


# http://www.ifnamemain.com/posts/2013/Dec/10/c_structs_python/


"""
Question for blackrock support:
   * possible to get interleave channels ?
   * chunksize (latency) ?
   * channel selection
   * chan_info.smpgroup  ??


"""



try:
    cdskkdll = ctypes.windll.cbsdk
    HAVE_BLACKROCK = True
except :
    cdskkdll = None
    HAVE_BLACKROCK = False


class CbSdkError( Exception ):
    def __init__(self, errno):
        self.errno = errno
        err_msg = ''
        #~ err_msg = ctypes.create_string_buffer(UL.ERRSTRLEN)
        #~ errno2 = _cbw.cbGetErrMsg(errno,err_msg)
        #~ assert errno2==0, Exception('_cbw.cbGetErrMsg do not work')
        errstr = 'CbSdkError %d: %s'%(errno,err_msg.value)                
        Exception.__init__(self, errstr)




def decorate_with_error(f):
    def func_with_error(*args):
        errno = f(*args)
        if errno != CBSDKRESULT_SUCCESS:
            raise CbSdkError(errno)
        return errno
    return func_with_error

class CBSDK:
    def __getattr__(self, attr):
        f = getattr(cdskkdll, 'cbSdk'+attr)
        return decorate_with_error(f)


if HAVE_BLACKROCK:
    cbSdk = CBSDK()



class Blackrock(Node):
    """Simple wrapper on top of cbsdk.dll provide by BlackRock micro system.
    To get signal for the CB system.
    """
    
    _output_specs = {
        'aichannels': {}
    }
    
    def __init__(self, **kargs):
        Node.__init__(self, **kargs)
        assert HAVE_BLACKROCK, "Imposible to found DLL: cbsdk.dll"

    def _configure(self,):
        pass
    
    def _initialize(self, ai_channels=[], nInstance=0):
        """
        ai_channels are blackrock channel 1-based
        
        """
        self.nInstance = nInstance
        cbSdk.Open(self.nInstance, CBSDKCONNECTION_DEFAULT)
        
        # configure channels
        for ai_channel in ai_channels:
            chan_info = cbPKT_CHANINFO()
            cbSdk.GetChannelConfig(self.nInstance, ctype.c_short(ai_channel), ctypes.byref(chan_info))
            chan_info.smpgroup = 5 # continuous sampling rate (30kHz)
            cbSdk.SetChannelConfig(self.nInstance, ctype.c_short(ai_channel), ctypes.byref(chan_info))
        
        # configure continuous acq
            #~ CBSDKAPI    cbSdkResult cbSdkSetTrialConfig(UINT32 self.nInstance,
                             #~ UINT32 bActive, UINT16 begchan = 0, UINT32 begmask = 0, UINT32 begval = 0,
                             #~ UINT16 endchan = 0, UINT32 endmask = 0, UINT32 endval = 0, bool bDouble = false,
                             #~ UINT32 uWaveforms = 0, UINT32 uConts = cbSdk_CONTINUOUS_DATA_SAMPLES, UINT32 uEvents = cbSdk_EVENT_DATA_SAMPLES,
                             #~ UINT32 uComments = 0, UINT32 uTrackings = 0, bool bAbsolute = false); // Configure a data collection trial
        cbSdk.SetTrialConfig(self.nInstance, 1, 0, 0, 0, 0, 0, 0, false, 0, cbSdk_CONTINUOUS_DATA_SAMPLES, 0, 0, 0, true)
        
        # create structure to hold the data
        # here contrary to example in CPP I create only one buffer
        # that will be sliced in continuous arrays
        self.trial = cbSdkTrialCont()
        self.ai_buffer = np.zeros((cbNUM_ANALOG_CHANS, cbSdk_CONTINUOUS_DATA_SAMPLES, ), dtype='int16')
        for i in range(cbNUM_ANALOG_CHANS):
            arr = self._ai_buffer[i]
            # TODO test if continuous
            self.trial.samples[i] = np.ctypeslib.as_ctypes(arr)
        
        self.thread = BlackrockThread(self, parent=None)

    def _start(self):
        self.thread.start()

    def _stop(self):
        self.thread.stop()
        self.thread.wait()
        cbSdk.Close(self.nInstance)
        

    def _close(self):
        pass




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
        trial = self.node.trial
        ai_buffer = self.node.ai_buffer
        
        n = 0
        while True:
            with self.lock:
                if not self.running:
                    break
            
            #~ CBSDKAPI    cbSdkResult cbSdkGetTrialData(UINT32 nInstance,
                                          #~ UINT32 bActive, cbSdkTrialEvent * trialevent, cbSdkTrialCont * trialcont,
                                          #~ cbSdkTrialComment * trialcomment, cbSdkTrialTracking * trialtracking);            
            
            cbSdk.GetTrialData(self.nInstance, 1, None, ctypes.byref(trial), None, None)
            
            # since internanlly the memory layout is chanXsample we swap it
            data = ai_buffer.T.copy()
            n += data.shape[0]
            stream.send(data, index=n)

    def stop(self):
        with self.lock:
            self.running = False



register_node_type(Blackrock)


# constant and Struct

CBSDKRESULT_SUCCESS = 0
cbNUM_ANALOG_CHANS = 256 + 16
cbSdk_CONTINUOUS_DATA_SAMPLES = 102400


# for convinient translation
INT32 = ctypes.c_int32
UINT32 = ctypes.c_uint32
INT16 = ctypes.c_int16
UINT16 = ctypes.c_uint16
INT8 = ctypes.c_int8
UINT8 = ctypes.c_uint8
CHAR = ctypes.c_char






class cbSCALING(ctypes.Structure):
    _fields_ = [
        ('digmin', INT16),
        ('digmax', INT16),
        ('anamin', INT32),
        ('anamax', INT32),
        ('anagain', INT32),
        ('anaunit', CHAR*8),
    ]

class cbFILTDESC(ctypes.Structure):
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
    _fields_ = [
        ('nOverride', INT16),
        ('afOrigin', INT16*3),
        ('afShape', (INT16*3)*3),
        ('aPhi', INT16),
        ('bValid', UINT32),
    ]

class cbHOOP(ctypes.Structure):
    _fields_ = [
        ('valid', UINT16),
        ('time', INT16),
        ('min', INT16),
        ('max', INT16),
    ]


class cbPKT_CHANINFO(ctypes.Structure):
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



class cbSdkTrialCont(ctypes.Structure):
    _fields_ = [
        ('count', UINT16),
        ('chan', (UINT16 * cbNUM_ANALOG_CHANS)),
        ('sample_rates', (UINT16 * cbNUM_ANALOG_CHANS)),
        ('num_samples', (UINT32 * cbNUM_ANALOG_CHANS)),
        ('time', UINT32),
        ('samples', (ctypes.c_void_p * cbNUM_ANALOG_CHANS)),
    ]

