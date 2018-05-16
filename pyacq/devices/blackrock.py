import numpy as np
import logging
import ctypes
import os

#~ from ..core import Node, register_node_type, ThreadPollInput
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
except WindowsError:
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
    
    def _initialize(self, ai_channels=[], self.nInstance=0):
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
        for i in range(cbNUM_ANALOG_CHANS:
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



register_node_type(NIDAQmx)


# constant and Struct

CBSDKRESULT_SUCCESS = 0
cbNUM_ANALOG_CHANS = 256 + 16
cbSdk_CONTINUOUS_DATA_SAMPLES = 102400


# for convinient translation
#~ UINT32 = ctypes.c_ulong
#~ UINT16 = ctypes.c_ushort
#~ UINT8 = ctypes.c_ubyte


#~ typedef struct {
    #~ UINT32     time;           // system clock timestamp
    #~ UINT16     chid;           // 0x8000
    #~ UINT8   type;           // cbPKTTYPE_AINP*
    #~ UINT8   dlen;           // cbPKT_DLENCHANINFO

    #~ UINT32     chan;           // actual channel id of the channel being configured
    #~ UINT32     proc;           // the address of the processor on which the channel resides
    #~ UINT32     bank;           // the address of the bank on which the channel resides
    #~ UINT32     term;           // the terminal number of the channel within it's bank
    #~ UINT32     chancaps;       // general channel capablities (given by cbCHAN_* flags)
    #~ UINT32     doutcaps;       // digital output capablities (composed of cbDOUT_* flags)
    #~ UINT32     dinpcaps;       // digital input capablities (composed of cbDINP_* flags)
    #~ UINT32     aoutcaps;       // analog output capablities (composed of cbAOUT_* flags)
    #~ UINT32     ainpcaps;       // analog input capablities (composed of cbAINP_* flags)
    #~ UINT32     spkcaps;        // spike processing capabilities
    #~ cbSCALING  physcalin;      // physical channel scaling information
    #~ cbFILTDESC phyfiltin;      // physical channel filter definition
    #~ cbSCALING  physcalout;     // physical channel scaling information
    #~ cbFILTDESC phyfiltout;     // physical channel filter definition
    #~ char       label[cbLEN_STR_LABEL];   // Label of the channel (null terminated if <16 characters)
    #~ UINT32     userflags;      // User flags for the channel state
    #~ INT32      position[4];    // reserved for future position information
    #~ cbSCALING  scalin;         // user-defined scaling information for AINP
    #~ cbSCALING  scalout;        // user-defined scaling information for AOUT
    #~ UINT32     doutopts;       // digital output options (composed of cbDOUT_* flags)
    #~ UINT32     dinpopts;       // digital input options (composed of cbDINP_* flags)
    #~ UINT32     aoutopts;       // analog output options
    #~ UINT32     eopchar;        // digital input capablities (given by cbDINP_* flags)
    #~ union {
        #~ struct {
            #~ UINT32              monsource;      // address of channel to monitor
            #~ INT32               outvalue;       // output value
        #~ };
        #~ struct {
            #~ UINT16              lowsamples;     // address of channel to monitor
            #~ UINT16              highsamples;    // address of channel to monitor
            #~ INT32               offset;         // output value
        #~ };
    #~ };
    #~ UINT8				trigtype;		// trigger type (see cbDOUT_TRIGGER_*)
    #~ UINT16				trigchan;		// trigger channel
    #~ UINT16				trigval;		// trigger value
    #~ UINT32              ainpopts;       // analog input options (composed of cbAINP* flags)
    #~ UINT32              lncrate;          // line noise cancellation filter adaptation rate
    #~ UINT32              smpfilter;        // continuous-time pathway filter id
    #~ UINT32              smpgroup;         // continuous-time pathway sample group
    #~ INT32               smpdispmin;       // continuous-time pathway display factor
    #~ INT32               smpdispmax;       // continuous-time pathway display factor
    #~ UINT32              spkfilter;        // spike pathway filter id
    #~ INT32               spkdispmax;       // spike pathway display factor
    #~ INT32               lncdispmax;       // Line Noise pathway display factor
    #~ UINT32              spkopts;          // spike processing options
    #~ INT32               spkthrlevel;      // spike threshold level
    #~ INT32               spkthrlimit;      //
    #~ UINT32              spkgroup;         // NTrodeGroup this electrode belongs to - 0 is single unit, non-0 indicates a multi-trode grouping
    #~ INT16               amplrejpos;       // Amplitude rejection positive value
    #~ INT16               amplrejneg;       // Amplitude rejection negative value
    #~ UINT32              refelecchan;      // Software reference electrode channel
    #~ cbMANUALUNITMAPPING unitmapping[cbMAXUNITS];            // manual unit mapping
    #~ cbHOOP              spkhoops[cbMAXUNITS][cbMAXHOOPS];   // spike hoop sorting set
#~ } cbPKT_CHANINFO;



    #~ ('time', UINT32),
    #~ ('chid', UINT16),
    #~ ('type', UINT8),
    #~ ('dlen', UINT8),
    #~ ('chan', UINT32),
    #~ ('proc', UINT32),
    #~ ('bank', UINT32),
    #~ ('term', UINT32),
    #~ ('chancaps', UINT32),
    #~ ('doutcaps', UINT32),
    #~ ('dinpcaps', UINT32),
    #~ ('aoutcaps', UINT32),
    #~ ('ainpcaps', UINT32),
    #~ ('spkcaps', UINT32),
    #~ ('physcalin', cbSCALING),
    #~ ('phyfiltin', cbFILTDESC),
    #~ ('physcalout', cbSCALING),
    #~ ('phyfiltout', cbFILTDESC),
    #~ ('label', c_char * 16),
    #~ ('userflags', UINT32),
    #~ ('position', INT32 * 4),
    #~ ('scalin', cbSCALING),
    #~ ('scalout', cbSCALING),
    #~ ('doutopts', UINT32),
    #~ ('dinpopts', UINT32),
    #~ ('aoutopts', UINT32),
    #~ ('eopchar', UINT32),
    #~ ('unnamed_1', union_anon_42),
    #~ ('trigtype', UINT8),
    #~ ('trigchan', UINT16),
    #~ ('trigval', UINT16),
    #~ ('ainpopts', UINT32),
    #~ ('lncrate', UINT32),
    #~ ('smpfilter', UINT32),
    #~ ('smpgroup', UINT32),
    #~ ('smpdispmin', INT32),
    #~ ('smpdispmax', INT32),
    #~ ('spkfilter', UINT32),
    #~ ('spkdispmax', INT32),
    #~ ('lncdispmax', INT32),
    #~ ('spkopts', UINT32),
    #~ ('spkthrlevel', INT32),
    #~ ('spkthrlimit', INT32),
    #~ ('spkgroup', UINT32),
    #~ ('amplrejpos', INT16),
    #~ ('amplrejneg', INT16),
    #~ ('refelecchan', UINT32),
    #~ ('unitmapping', cbMANUALUNITMAPPING * 5),
    #~ ('spkhoops', (cbHOOP * 4) * 5),


class cbPKT_CHANINFO(ctypes.Structure):
    _fields_ = [
        ('time', UINT32), # system clock timestamp
        ('chid', UINT16), # 0x8000
        ('type', UINT8), # cbPKTTYPE_AINP*
        ('dlen', UINT8), # cbPKT_DLENCHANINFO
        
        ('chan', UINT32), # actual channel id of the channel being configured
        ('proc', UINT32), # the address of the processor on which the channel resides
        
    #~ UINT32     bank;           // the address of the bank on which the channel resides
    #~ UINT32     term;           // the terminal number of the channel within it's bank
    #~ UINT32     chancaps;       // general channel capablities (given by cbCHAN_* flags)
    #~ UINT32     doutcaps;       // digital output capablities (composed of cbDOUT_* flags)
    #~ UINT32     dinpcaps;       // digital input capablities (composed of cbDINP_* flags)
    #~ UINT32     aoutcaps;       // analog output capablities (composed of cbAOUT_* flags)
    #~ UINT32     ainpcaps;       // analog input capablities (composed of cbAINP_* flags)
    #~ UINT32     spkcaps;        // spike processing capabilities
    #~ cbSCALING  physcalin;      // physical channel scaling information
    #~ cbFILTDESC phyfiltin;      // physical channel filter definition
    #~ cbSCALING  physcalout;     // physical channel scaling information
    #~ cbFILTDESC phyfiltout;     // physical channel filter definition
    #~ char       label[cbLEN_STR_LABEL];   // Label of the channel (null terminated if <16 characters)
    #~ UINT32     userflags;      // User flags for the channel state
    #~ INT32      position[4];    // reserved for future position information
    #~ cbSCALING  scalin;         // user-defined scaling information for AINP
    #~ cbSCALING  scalout;        // user-defined scaling information for AOUT
    #~ UINT32     doutopts;       // digital output options (composed of cbDOUT_* flags)
    #~ UINT32     dinpopts;       // digital input options (composed of cbDINP_* flags)
    #~ UINT32     aoutopts;       // analog output options
    #~ UINT32     eopchar;        // digital input capablities (given by cbDINP_* flags)
    #~ union {
        #~ struct {
            #~ UINT32              monsource;      // address of channel to monitor
            #~ INT32               outvalue;       // output value
        #~ };
        #~ struct {
            #~ UINT16              lowsamples;     // address of channel to monitor
            #~ UINT16              highsamples;    // address of channel to monitor
            #~ INT32               offset;         // output value
        #~ };
    #~ };
    #~ UINT8				trigtype;		// trigger type (see cbDOUT_TRIGGER_*)
    #~ UINT16				trigchan;		// trigger channel
    #~ UINT16				trigval;		// trigger value
    #~ UINT32              ainpopts;       // analog input options (composed of cbAINP* flags)
    #~ UINT32              lncrate;          // line noise cancellation filter adaptation rate
    #~ UINT32              smpfilter;        // continuous-time pathway filter id
    #~ UINT32              smpgroup;         // continuous-time pathway sample group
    #~ INT32               smpdispmin;       // continuous-time pathway display factor
    #~ INT32               smpdispmax;       // continuous-time pathway display factor
    #~ UINT32              spkfilter;        // spike pathway filter id
    #~ INT32               spkdispmax;       // spike pathway display factor
    #~ INT32               lncdispmax;       // Line Noise pathway display factor
    #~ UINT32              spkopts;          // spike processing options
    #~ INT32               spkthrlevel;      // spike threshold level
    #~ INT32               spkthrlimit;      //
    #~ UINT32              spkgroup;         // NTrodeGroup this electrode belongs to - 0 is single unit, non-0 indicates a multi-trode grouping
    #~ INT16               amplrejpos;       // Amplitude rejection positive value
    #~ INT16               amplrejneg;       // Amplitude rejection negative value
    #~ UINT32              refelecchan;      // Software reference electrode channel
    #~ cbMANUALUNITMAPPING unitmapping[cbMAXUNITS];            // manual unit mapping
    #~ cbHOOP              spkhoops[cbMAXUNITS][cbMAXHOOPS];   // spike hoop sorting set        
        
    ]



class cbSdkTrialCont(ctypes.Structure):
    _fields_ = [
        ('count', UINT16),
        ('chan', (UINT16 * cbNUM_ANALOG_CHANS)),
        ('sample_rates', (UINT16 * cbNUM_ANALOG_CHANS)),
        ('num_samples', (UINT32 * cbNUM_ANALOG_CHANS)),
        ('time', UINT32),
        ('samples', (c_void_p * cbNUM_ANALOG_CHANS)),
    ]

