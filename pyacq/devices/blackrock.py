import numpy as np
import logging
import ctypes
import os

#~ from ..core import Node, register_node_type, ThreadPollInput
from pyqtgraph.Qt import QtCore, QtGui
from pyqtgraph.util.mutex import Mutex

# http://www.ifnamemain.com/posts/2013/Dec/10/c_structs_python/


try:
    _cbsdk = ctypes.windll.cbsdk
    HAVE_BLACKROCK = True
except WindowsError:
    _cbsdk = None
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

class CbSdk:
    def __getattr__(self, attr):
        f = getattr(_cbsdk, attr)
        return decorate_with_error(f)


if HAVE_BLACKROCK:
    cbsdk = CbSdk()



class Blackrock(Node):
    """Simple wrapper on top of cbsdk.dll provide by BlackRock micro system.
    To get signal for the CB system.
    """
    def __init__(self, **kargs):
        Node.__init__(self, **kargs)
        assert HAVE_BLACKROCK, "Imposible to found DLL: cbsdk.dll"

    def _configure(self,):
        pass
    
    def _initialize(self):
        pass
        
        #~ cbSdkResult res = cbSdkOpen(0, CBSDKCONNECTION_DEFAULT);
        
        	#~ //setup the first channel only (continuous recording at 30kHz, no filter)
	#~ cbPKT_CHANINFO chan_info;
	#~ //get current channel configuration
	#~ cbSdkResult r = cbSdkGetChannelConfig(0, 1, &chan_info);
	#~ //change configuration
	#~ chan_info.smpgroup = 5; //continuous sampling rate (30kHz)
							#~ //set channel configuration
	#~ r = cbSdkSetChannelConfig(0, 1, &chan_info); //note: channels start at 1

												 #~ //ask to send trials (only continuous data)                                                                                                                                                 
	#~ res = cbSdkSetTrialConfig(0, 1, 0, 0, 0, 0, 0, 0, false, 0, cbSdk_CONTINUOUS_DATA_SAMPLES, 0, 0, 0, true);                                                                                                                                   
	#~ if (res != CBSDKRESULT_SUCCESS)                                                                                                                                                                                                                 
	#~ {
		#~ cout << "ERROR: cbSdkSetTrialConfig" << endl;
		#~ return 1;
	#~ }


    def _start(self):
        pass
    
    def _stop(self):
        pass
    
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
        
        aitask = self.node.aitask
        chunksize = self.node._chunksize
        buffer_time = chunksize / self.node._conf['sample_rate']
        aitask.in_stream.timeout = timeout = buffer_time*10.
        
        if self.node.magnitude_mode=='raw':
            raw_data = np.zeros((chunksize, self.node._nb_ai_channel), dtype='int16')
            raw_data_flat = raw_data
            raw_data_flat.reshape(-1)
        else:
            data_float64 = np.zeros((self.node._nb_ai_channel, chunksize), dtype='float64')
        
        
        stream = self.node.outputs['aichannels']
        
        n = 0
        while True:
            with self.lock:
                if not self.running:
                    break
            
            if self.node.magnitude_mode=='raw':
                nb_sample = aitask.in_stream.readinto(raw_data_flat)
                if nb_sample==0:
                    continue
                n += raw_data.shape[0]
                stream.send(raw_data, index=n)
            else:
                nb_sample = _read_analog_f_64(aitask._handle, data_float64, chunksize, timeout)
                if nb_sample==0:
                    continue
                scaled_data = np.require(data_float64.T, dtype=self.node._ai_dt, requirements='C')
                #~ scaled_data = data_float64.T.astype(self.node._ai_dt)
                n += scaled_data.shape[0]
                stream.send(scaled_data, index=n)

    def stop(self):
        with self.lock:
            self.running = False



register_node_type(NIDAQmx)


# constant and Struct

#~ CBSDKRESULT_SUCCESS = 0
#~ cbNUM_ANALOG_CHANS


#~ /// Trial continuous data
#~ typedef struct _cbSdkTrialCont
#~ {
    #~ UINT16 count; ///< Number of valid channels in this trial (up to cbNUM_ANALOG_CHANS)
    #~ UINT16 chan[cbNUM_ANALOG_CHANS]; ///< Channel numbers (1-based)
    #~ UINT16 sample_rates[cbNUM_ANALOG_CHANS]; ///< Current sample rate (samples per second)
    #~ UINT32 num_samples[cbNUM_ANALOG_CHANS]; ///< Number of samples
    #~ UINT32 time;  ///< Start time for trial continuous data
    #~ void * samples[cbNUM_ANALOG_CHANS]; ///< Buffer to hold sample vectors
#~ } cbSdkTrialCont;

