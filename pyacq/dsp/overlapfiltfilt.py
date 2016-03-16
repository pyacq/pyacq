from pyqtgraph.Qt import QtCore
import pyqtgraph as pg
import weakref
import numpy as np

from ..core import (Node, register_node_type, ThreadPollInput)
from ..core.stream import SharedArraySender

import distutils.version
try:
    import scipy.signal
    HAVE_SCIPY = True
    # scpy.signal.sosfilt was introduced in scipy 0.16
    assert distutils.version.LooseVersion(scipy.__version__)>'0.16'
except ImportError:
    HAVE_SCIPY = False


class OverlapFiltfiltThread(ThreadPollInput):
    def __init__(self, input_stream, output_stream, chunksize, overlapsize, timeout = 200, parent = None):
        ThreadPollInput.__init__(self, input_stream, timeout = timeout, parent = parent)
        self.output_stream = weakref.ref(output_stream)
        self.chunksize = chunksize
        self.overlapsize = overlapsize
        
        #internal buffer
        self.internal_buffer = SharedArraySender
        

    def process_data(self, pos, data):
        if data is None:
            #sharred_array case
            data =  self.input_stream().get_array_slice(pos, None)
        
        data_filtered, self.zi = scipy.signal.sosfilt(self.coefficients, data, zi = self.zi, axis = 0)
        self.output_stream().send(pos, data_filtered)
        
    def set_params(self, coefficients, nb_channel, dtype):
        self.coefficients = coefficients
        self.n_sections = coefficients.shape[0]
        self.zi = np.zeros((self.n_sections, 2, nb_channel), dtype= dtype)



class OverlapFiltfilt(Node,  QtCore.QObject):
    """
    Node for filtering with forward-backward method (filtfilt).
    This use sliding overlap technics.
    
    The chunksize and the overlapsize are important for the accuracy of filtering.
    You need to study them carfully, otherwise the result should be the same as a
    real filtfilt ona long term signal. You must check the residual between real offline filtfitl
    and this online OverlapFiltfilt.
    Note that the chunksize have a strong effect on low frequency.
    
    This uses Second Order (sos) coeeficient.
    It internally use scipy.signal.sosfilt which is available only on scipy >0.16
    
    
    The chunksize need to be fixed.
    For overlapsize there are 2 cases:
      1-  overlapsize<chunksize/2 : natural case. each chunk partailly overlap. 
            The overlap are on sides, the central part come from one chunk.
      2 - overlapsize>chunksize/2: chunk are fully averlapping. There is no central part.
    In the 2 cases, for each arrival of new chunk at [-chunksize:], 
    the computed chunk at [-(chunksize+overlapsize):-overlapsize] is released.
    
    """
    
    _input_specs = {'signals' : dict(streamtype = 'signals')}
    _output_specs = {'signals' : dict(streamtype = 'signals')}
    
    def __init__(self, parent = None, **kargs):
        QtCore.QObject.__init__(self, parent)
        Node.__init__(self, **kargs)
        assert HAVE_SCIPY, "SosFilter need scipy>0.16"
    
    def _configure(self, chunksize=1024, overlapsize=512, coefficients = None):
        """
        Set the coefficient of the filter.
        See http://scipy.github.io/devdocs/generated/scipy.signal.sosfilt.html for details.
        """
        self.chunksize = chunksize
        self.overlapsize = overlapsize
        self.set_coefficients(coefficients)

    def after_input_connect(self, inputname):
        self.nb_channel = self.input.params['nb_channel']
        for k in ['sample_rate', 'dtype', 'nb_channel', 'shape', 'timeaxis']:
            self.output.spec[k] = self.input.params[k]
    
    def _initialize(self):
        self.thread = OverlapFiltfiltThread(self.input, self.output, self.chunksize, self.overlapsize)
        self.thread.set_params(self.coefficients, self.nb_channel, self.output.params['dtype'])
    
    def _start(self):
        self.thread.last_pos = None
        self.thread.start()
    
    def _stop(self):
        self.thread.stop()
        self.thread.wait()
    
    def set_coefficients(self, coefficients):
        self.coefficients = coefficients
        if self.initialized():
            self.thread.set_params(self.coefficients, self.nb_channel, self.output.params['dtype'])

register_node_type(SosFilter)