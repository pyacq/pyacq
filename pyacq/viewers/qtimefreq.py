from pyqtgraph.Qt import QtCore, QtGui
import pyqtgraph as pg

import numpy as np
import weakref

from ..core import (WidgetNode, Node, register_node_type,  InputStream,
        ThreadPollInput, StreamConverter, StreamSplitter)


try:
    import scipy.signal
    import scipy.fftpack
    HAVE_SCIPY = True
except ImportError:
    HAVE_SCIPY = False





default_params = [
        {'name': 'xsize', 'type': 'logfloat', 'value': 10., 'step': 0.1, 'limits' : (.1, 60)},
        {'name': 'nb_column', 'type': 'int', 'value': 1},
        {'name': 'background_color', 'type': 'color', 'value': 'k' },
        {'name': 'colormap', 'type': 'list', 'value': 'jet', 'values' : ['jet', 'gray', 'bone', 'cool', 'hot', ] },
        {'name': 'refresh_interval', 'type': 'int', 'value': 500 , 'limits':[5, 1000]},
        #~ {'name': 'display_labels', 'type': 'bool', 'value': False },
        {'name' : 'timefreq' , 'type' : 'group', 'children' : [
                        {'name': 'f_start', 'type': 'float', 'value': 3., 'step': 1.},
                        {'name': 'f_stop', 'type': 'float', 'value': 90., 'step': 1.},
                        {'name': 'deltafreq', 'type': 'float', 'value': 3., 'step': 1.,  'limits' : (0.1, 1.e6)},
                        {'name': 'f0', 'type': 'float', 'value': 2.5, 'step': 0.1},
                        {'name': 'normalisation', 'type': 'float', 'value': 0., 'step': 0.1},]}
    ]

default_by_channel_params = [ 
                {'name': 'visible', 'type': 'bool', 'value': True},
                {'name': 'clim', 'type': 'float', 'value': 10.},
            ]


    


class QTimeFreq(WidgetNode):
    """
    Class to visulaize time-frequency morlet scalogram for multiple signal.
    
    The QTimeFreq need as inputstream:
        * transfermode==sharedarray
        * timeaxis==1
    
    If the inputstream has not this propertis  the class create it own proxy input
    with a node StreamConverter.
    
    """
    
    _input_specs = {'signal' : dict(streamtype = 'signals', shape = (-1), )}
    
    _default_params = default_params
    _default_by_channel_params = default_by_channel_params
    
    def __init__(self, **kargs):
        WidgetNode.__init__(self, **kargs)
        
        self.layout = QtGui.QHBoxLayout()
        self.setLayout(self.layout)
        
        self.grid = QtGui.QGridLayout()
        self.mainlayout.addLayout(self.grid)
        
        self.graphicsviews = []
    
    def show_params_controler(self):
        self.params_controler.show()
        #TODO deal with modality
    
    def _configure(self, with_user_dialog = True, max_xsize = 60.):
        self.with_user_dialog = with_user_dialog
        self.max_xsize = max_xsize
    
    def _initialize(self):
        d0, d1 = self.input.params['shape']
        if self.input.params['timeaxis']==0:
            self.nb_channel  = d1
        else:
            self.nb_channel  = d0
        
        #create splitter and worker
        self.splitter = StreamSplitter()
        self.splitter.configure(nb_channel = self.nb_channel)
        splitter.input.connect(self.input)
        self.workers = []
        self.pollers =[]
        for i in range(self.nb_channel):
            self.splitter.outputs[str(i)].configure(shape = (-1, 1))#TODO put some stream_spec
            
            worker = TimeFreqCompute()
            worker.configure(max_xsize = self.max_size)
            worker.input.connect(self.splitter.outputs[str(i)])
            worker.output.configure()#TODO put some stream_spec
            worker.initialize()
            self.workers.append(worker)
            
            poller = ThreadPollInput(input_stream = worker.output)
            self.poller.new_data.connect(self._on_new_map)
            poller.i = i
            self.pollers.append(poller)
        self.splitter.initialize()
        
        # Create parameters
        all = [ ]
        for i in range(self.nb_channel):
            name = 'Signal{}'.format(i)
            all.append({ 'name': name, 'type' : 'group', 'children' : self._default_by_channel_params})
        self.by_channel_params = pg.parametertree.Parameter.create(name='AnalogSignals', type='group', children=all)
        self.params = pg.parametertree.Parameter.create( name='Global options',
                                                    type='group', children =self._default_params)
        self.all_params = pg.parametertree.Parameter.create(name = 'all param',
                                    type = 'group', children = [self.params,self.by_channel_params  ])
        self.all_params.sigTreeStateChanged.connect(self.on_param_change)
        self.params.param('xsize').setLimits([16./sr, self.max_xsize*.95]) 
        
        if self.with_user_dialog:
            #~ self.params_controler = TimeFreqControler(parent = self, viewer = self)
            #~ self.params_controler.setWindowFlags(QtCore.Qt.Window)
            #~ self.viewBox.doubleclicked.connect(self.show_params_controler)
            pass
        else:
            self.params_controler = None
        
        
        self.create_grid()
        self.initialize_time_freq()
        
        
    def _start(self):
        self.splitter.start()
        for worker in self.workers:
            worker.start()
    
    def _stop(self):
        for worker in self.workers:
            worker.stop()        
        self.splitter.stop()
    
    def _close(self):
        for worker in self.workers:
            worker.close()        
        self.splitter.close()

    def create_grid(self):
        if sip.isdeleted(self): 
            # This is very ugly patch but
            # When a TimeFreq is detroyer sometime the init is not fichised!!!
            return
        
        color = self.params['background_color']
        for graphicsview in self.graphicsviews:
            if graphicsview is not None:
                graphicsview.hide()
                self.grid.removeWidget(graphicsview)
        self.plots =  [ None ] * self.nb_channel
        self.graphicsviews =  [ None ] * self.nb_channel
        self.images = [ None ] * self.nb_channel
        r,c = 0,0
        for i in range(self.stream['nb_channel']):
            if not self.by_channel_params.children()[i]['visible']: continue

            viewBox = MyViewBox()
            if self.with_user_dialog:
                viewBox.doubleclicked.connect(self.show_params_controler)
            self.viewBox.gain_zoom.connect(self.clim_zoom)
            self.viewBox.xsize_zoom.connect(self.xsize_zoom)
            
            graphicsview  = pg.GraphicsView()
            graphicsview.setBackground(color)
            plot = pg.PlotItem(viewBox = viewBox)
            #~ plot.setTitle(self.stream['channel_names'][i])#TODO
            graphicsview.setCentralItem(plot)
            self.graphicsviews[i] = graphicsview
            
            self.plots[i] = plot
            self.grid.addWidget(graphicsview, r,c)
            
            c+=1
            if c==self.params['nb_column']:
                c=0
                r+=1
    
    def initialize_time_freq(self):
        tfr_params = self.params['timefreq'].children()
        #TODO
        
    
    def initialize_plots(self):
        pass
        #TODO
    
    def _on_new_map(self, pos, data):
        i = self.sender().i
        #TODO refresh one image
    
    def on_param_change(self):
        for param, change, data in changes:
            if change != 'value': continue
            if param.name()=='background_color':
                color = data
                for graphicsview in self.graphicsviews:
                    if graphicsview is not None:
                        graphicsview.setBackground(color)
            if param.name()=='xsize':
                self.initialize_time_freq()
            if param.name()=='colormap':
                self.initialize_time_freq()
            if param.name()=='nb_column':
                self.change_grid()
            if param.name()=='refresh_interval':
                self.timer.setInterval(data)
                
    def clim_zoom(self, factor):
        #TODO
        #~ for i, p in enumerate(self.viewer.paramChannels.children()):
            #~ p.param('clim').setValue(p.param('clim').value()*factor)
        pass
        
    def xsize_zoom(self, xmove):
        factor = xmove/100.
        newsize = self.params['xsize']*(factor+1.)
        limits = self.params.param('xsize').opts['limits']
        if newsize>limits[0] and newsize<limits[1]:
            self.params['xsize'] = newsize    
    
        
register_node_type(QTimeFreqViewer)



def generate_wavelet_fourier(len_wavelet, f_start, f_stop, deltafreq, sampling_rate, f0, normalisation):
    """
    Compute the wavelet coefficients at all scales and makes its Fourier transform.
    
    Parameters
    ----------
    len_wavelet : int
        length in sample of the windows
    f_start: float
        First frequency in Hz
    f_stop: float
        Last frequency in Hz
    deltafreq:
        Frequency interval in Hz
    sampling_rate:
        Sampling rate in Hz
    
    Returns:
    ----------
        wf : Fourier transform of the wavelet coefficients (after weighting)
              axis 0 is time,  axis 1 is freq
    """
    # compute final map scales
    scales = f0/np.arange(f_start,f_stop,deltafreq)*sampling_rate
    
    # compute wavelet coeffs at all scales
    xi=np.arange(-len_wavelet/2.,len_wavelet/2.)
    xsd = xi[:,np.newaxis] / scales
    wavelet_coefs=np.exp(complex(1j)*2.*np.pi*f0*xsd)*np.exp(-np.power(xsd,2)/2.)

    weighting_function = lambda x: x**(-(1.0+normalisation))
    wavelet_coefs = wavelet_coefs*weighting_function(scales[np.newaxis,:])

    # Transform the wavelet into the Fourier domain
    wf=scipy.fftpack.fft(wavelet_coefs,axis=0)
    wf=wf.conj()
    
    return wf


class TimeFreqCompute(Node):
    """
    TimeFreqCompute compute a wavelet scalogram every X interval and
    send it to QTimeFreqViewer.
    """
    _input_specs = {'signal' : dict(streamtype = 'signals', shape = (-1), )}
    _output_specs = {'timefreq' : dict(streamtype = 'image', dtype = 'float32')}
    
    def __init__(self, **kargs):
        Node.__init__(self, **kargs)
        assert HAVE_SCIPY, "TimeFreqCompute node depends on the `scipy` package, but it could not be imported."
    
    def _configure(self, max_xsize = 60.):
        self.max_xsize = max_xsize
    
    def _initialize(self):
        sr = self.input.params['sampling_rate']
        assert len(self.input.params['shape']) == 2, 'Wrong shape: TimeFreqCompute'
        d0, d1 = self.input.params['shape']
        if self.input.params['timeaxis']==0:
            self.nb_channel  = d1
            sharedarray_shape = (int(sr*self.max_xsize), self.nb_channel)
        else:
            self.nb_channel  = d0
            sharedarray_shape = (self.nb_channel, int(sr*self.max_xsize)),
        assert self.nb_channel == 1, 'Wrong nb_channel: TimeFreqCompute work for one channel only'
        
        
        #create proxy input
        if self.input.params['transfermode'] == 'sharedarray':
            self.proxy_input = self.input
            self.conv = None
        else:
            # if input is not transfermode creat a proxy
            self.conv = StreamConverter()
            self.conv.configure()
            self.conv.input.connect(self.input.params)
            self.conv.output.configure(protocol='inproc', interface='127.0.0.1', port='*', 
                   transfermode = 'sharedarray', streamtype = 'analogsignal',
                   dtype='float32', shape=self.input.params['shape'], timeaxis=self.input.params['timeaxis'],
                   compression='', scale=None, offset=None, units='',
                   sharedarray_shape=sharedarray_shape, ring_buffer_method='double',
                   )
            self.conv.initialize()
            self.proxy_input = InputStream()
            self.proxy_input.connect(self.conv.output)
        
        #poller
        self.poller = ThreadPollInput(input_stream = self.proxy_input)
        self.poller.new_data.connect(self._on_new_data)
        #timer
        self._head = 0
        self.timer = QtCore.QTimer(singleShot=False, interval = 500)
        self.timer.timeout.connect(self.compute)
        
        self.wavelet_fourrier = None

    def _start(self):
        self._n = 0
        if self.conv is not None:
            self.conv.start()
        self.poller.start()
        self.timer.start()
    
    def _stop(self):
        if self.conv is not None:
            self.conv.stop()
        self.poller.stop()
        self.timer.stop()
    
    def _close(self):
        if self.running():
            self.stop()

    def _on_new_data(self, pos, data):
        self._head = pos
        
    def on_fly_change_wavelet(self, wavelet_fourrier=None, downsampling_factor=None, sig_chunk_size = None,
            plot_length=None, filter_a=None, filter_b=None):
        """
        This can be call by RPC but it can be slow due to wavelet_fourrier size.
        
        Note that for optimization purpose wavelet_fourrier.shape[0] should be 2**N because
        it is fft based.
        
        """
        self.wavelet_fourrier = wavelet_fourrier
        self.downsampling_factor = downsampling_factor
        self.sig_chunk_size = sig_chunk_size
        self.plot_length = plot_length
        self.filter_a = filter_a
        self.filter_b = filter_b
    
    def compute(self):
        if self.wavelet_fourrier is None: 
            # not on_fly_change_wavelet yet
            return

        head = self._head
        if self.downsampling_factor>1:
            head = head - head%self.downsampling_factor
        full_arr = self.proxy_input.get_array_slice(head, self.sig_chunk_size).reshape(-1)
        
        
        if self.downsampling_factor>1:
            small_arr = scipy.signal.filtfilt(self.filter_b, self.filter_a, full_arr)
            small_arr =small_arr[::self.downsampling_factor].copy()# to ensure continuity
        else:
            small_arr = full_arr
        small_arr_f=scipy.fftpack.fft(small_arr)
        wt_tmp=scipy.fftpack.ifft(small_arr_f[:,np.newaxis]*self.wavelet_fourrier,axis=0)
        wt = scipy.fftpack.fftshift(wt_tmp,axes=[0])
        wt = np.abs(wt).astype(self.output.params['dtype'])
        wt = wt[-self.plot_length:]
        
        #send map
        self._n += 1
        self.output.send(self._n, wt)

register_node_type(TimeFreqCompute)