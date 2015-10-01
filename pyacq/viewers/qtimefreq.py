from pyqtgraph.Qt import QtCore, QtGui
import pyqtgraph as pg
from pyqtgraph.util.mutex import Mutex

import numpy as np
import weakref
import time
from collections import OrderedDict

from ..core import (WidgetNode, Node, register_node_type,  InputStream, OutputStream,
        ThreadPollInput, StreamConverter, StreamSplitter)

from .qoscilloscope import MyViewBox

try:
    import scipy.signal
    import scipy.fftpack
    HAVE_SCIPY = True
except ImportError:
    HAVE_SCIPY = False


default_params = [
        {'name': 'xsize', 'type': 'float', 'value': 10., 'step': 0.1, 'limits' : (.1, 60)},
        {'name': 'nb_column', 'type': 'int', 'value': 1},
        {'name': 'background_color', 'type': 'color', 'value': 'k' },
        {'name': 'colormap', 'type': 'list', 'value': 'jet', 'values' : ['jet', 'gray', 'bone', 'cool', 'hot', ] },
        {'name': 'refresh_interval', 'type': 'int', 'value': 500 , 'limits':[5, 1000]},
        #~ {'name': 'display_labels', 'type': 'bool', 'value': False }, #TODO when title
        {'name' : 'timefreq' , 'type' : 'group', 'children' : [
                        {'name': 'f_start', 'type': 'float', 'value': 3., 'step': 1.},
                        {'name': 'f_stop', 'type': 'float', 'value': 90., 'step': 1.},
                        {'name': 'deltafreq', 'type': 'float', 'value': 3., 'step': 1.,  'limits' : [0.1, 1.e6]},
                        {'name': 'f0', 'type': 'float', 'value': 2.5, 'step': 0.1},
                        {'name': 'normalisation', 'type': 'float', 'value': 0., 'step': 0.1},]}
    ]

default_by_channel_params = [ 
                {'name': 'visible', 'type': 'bool', 'value': True},
                {'name': 'clim', 'type': 'float', 'value': 1.},
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
        
        self.mainlayout = QtGui.QHBoxLayout()
        self.setLayout(self.mainlayout)
        
        self.graphiclayout =  pg.GraphicsLayoutWidget()
        self.mainlayout.addWidget(self.graphiclayout)
        
        #~ self.grid = QtGui.QGridLayout()
        #~ self.mainlayout.addLayout(self.grid)
        
        #~ self.graphicsviews = []
    
    def show_params_controler(self):
        self.params_controler.show()
        #TODO deal with modality
    
    def _configure(self, with_user_dialog = True, max_xsize = 60., nodegroup_friends = None):
        self.with_user_dialog = with_user_dialog
        self.max_xsize = max_xsize
        self.nodegroup_friends = nodegroup_friends
        self.local_workers = self.nodegroup_friends is None
        
    
    def _initialize(self, ):
        self.sampling_rate = sr = self.input.params['sampling_rate']
        d0, d1 = self.input.params['shape']
        if self.input.params['timeaxis']==0:
            self.nb_channel  = d1
        else:
            self.nb_channel  = d0
        
        #create proxy input to ensure sharedarray with time axis 1
        if self.input.params['transfermode'] == 'sharedarray' and self.input.params['timeaxis'] == 1:
            self.conv = None
            self.proxy_input = self.input
        else:
            # if input is not transfermode creat a proxy
            if self.local_workers:
                self.conv = StreamConverter()
            else:
                ng = self.nodegroup_friends[-1]
                self.conv = ng.create_node('StreamConverter')
            
            self.conv.configure()


            #~ self.conv.input.connect(self.input.params)
            # the inputstream is not needed except for parameters
            stream_spec = dict(self.input.params)
            self.conv.input.connect(stream_spec)
            self.input.close()
            
            if self.input.params['timeaxis']==0:
                new_shape = (d1, d0)
            else:
                new_shape = (d0, d1)
            self.conv.output.configure(protocol = 'tcp', interface = '127.0.0.1', port='*', 
                   transfermode = 'sharedarray', streamtype = 'analogsignal',
                   dtype = 'float32', shape = new_shape, timeaxis = 1, 
                   compression ='', scale = None, offset = None, units = '',
                   sharedarray_shape = (self.nb_channel, int(sr*self.max_xsize)), ring_buffer_method = 'double',
                   )
            self.conv.initialize()

            self.proxy_input = InputStream()
            self.proxy_input.connect(self.conv.output)
        
        self.workers = []
        self.input_maps = []

        self.global_poller = ThreadPollInput(input_stream = self.proxy_input)
        self.global_timer = QtCore.QTimer(interval = 500)
        self.global_timer.timeout.connect(self.compute_maps)
        
        
        if self.local_workers:
            pass
        else:
            self.map_pollers = []
            
        
        for i in range(self.nb_channel):
            if self.local_workers:
                worker = TimeFreqWorker()
            else:
                ng = self.nodegroup_friends[i%(len(self.nodegroup_friends)-1)]
                worker = ng.create_node('TimeFreqWorker')
                
            worker.configure(max_xsize = self.max_xsize, channel = i, local = self.local_workers)
            worker.input.connect(self.conv.output)
            
            #TODO tcp or ipc or inproc
            if self.local_workers:
                # no output used
                worker.output.configure(protocol = 'inproc', transfermode = 'plaindata')
                worker.initialize()
                worker.wt_map_done.connect(self.on_new_map_local)
                #~ self.global_poller.new_data.connect(worker.back_compute.new_head)

                input_map = InputStream()
                stream_spec = dict(worker.output.params)
                #~ stream_spec['interface'] = 'neuro-090'
                #~ print(stream_spec)
                print(worker.output.params)
                input_map.connect(worker.output)
                self.input_maps.append(input_map)

                
            else:
                worker.output.configure(protocol = 'tcp', transfermode = 'plaindata')#, interface = 'eth0'
                worker.initialize()
                input_map = InputStream()
                stream_spec = dict(worker.output.params)
                #~ stream_spec['interface'] = 'neuro-090'
                #~ print(stream_spec)
                print(worker.output.params)
                input_map.connect(worker.output)
                self.input_maps.append(input_map)
                
                poller = ThreadPollInput(input_stream = input_map)
                poller.new_data.connect(self.on_new_map_socket)
                poller.i = i
                self.map_pollers.append(poller)
                
            self.workers.append(worker)
            
        
        #~ self.splitter.initialize()
        
        # This is used to diffred heavy action (setting plots, compute wavelet, ...)
        self.mutex_action = Mutex()
        self.actions = OrderedDict([(self.create_grid, False),
                                                    (self.initialize_time_freq, False),
                                                    (self.initialize_plots, False),
                                                    ])
        self.timer_action = QtCore.QTimer(singleShot=True, interval = 300)
        self.timer_action.timeout.connect(self.apply_actions)
        
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
        self.params.param('xsize').setLimits([16./sr, self.max_xsize*.95]) 
        self.all_params.sigTreeStateChanged.connect(self.on_param_change)
        
        if self.with_user_dialog:
            self.params_controler = TimeFreqControler(parent = self, viewer = self)
            self.params_controler.setWindowFlags(QtCore.Qt.Window)
        else:
            self.params_controler = None
        
        self.create_grid()
        self.initialize_time_freq()
        self.initialize_plots()
        
    def _start(self):
        #~ self.start_workers()
        self.global_poller.start()
        self.global_timer.start()
        if self.local_workers:
            pass
        else:
            for i in range(self.nb_channel):
                self.map_pollers[i].start()
        self.conv.start()
    
    def _stop(self):
        #~ self.stop_workers()
        self.global_timer.stop()
        self.global_poller.stop()
        self.global_poller.wait()
        if self.local_workers:
            pass
        else:
            for i in range(self.nb_channel):
                self.map_pollers[i].stop()
                self.map_pollers[i].wait()
        self.conv.stop()
    
    def _close(self):
        if self.running():
            self.stop()
        if self.with_user_dialog:
            self.params_controler.close()
        for worker in self.workers:
            worker.close()
        for poller in self.map_pollers:
            poller.close()
        self.conv.close()

    def create_grid(self):
        color = self.params['background_color']
        self.graphiclayout.clear()
        self.plots =  [ None ] * self.nb_channel
        self.images = [ None ] * self.nb_channel
        r,c = 0,0
        nb_visible =sum(self.by_channel_params.children()[i]['visible'] for i in range(self.nb_channel)) 
        rowspan = self.params['nb_column']
        colspan = nb_visible//self.params['nb_column']
        self.graphiclayout.ci.currentRow = 0
        self.graphiclayout.ci.currentCol = 0        
        for i in range(self.nb_channel):
            if not self.by_channel_params.children()[i]['visible']: continue

            viewBox = MyViewBox()
            if self.with_user_dialog:
                viewBox.doubleclicked.connect(self.show_params_controler)
            viewBox.gain_zoom.connect(self.clim_zoom)
            viewBox.xsize_zoom.connect(self.xsize_zoom)
            
            plot = pg.PlotItem(viewBox = viewBox)
            plot.hideButtons()

            plot.showAxis('left', False)
            plot.showAxis('bottom', False)
            
            self.graphiclayout.ci.layout.addItem(plot, r, c)#, rowspan, colspan)
            if r not in self.graphiclayout.ci.rows:
                self.graphiclayout.ci.rows[r] = {}
            self.graphiclayout.ci.rows[r][c] = plot
            self.graphiclayout.ci.items[plot] = [(r,c)]
            self.plots[i] = plot
            c+=1
            if c==self.params['nb_column']:
                c=0
                r+=1
    
    def initialize_time_freq(self):
        tfr_params = self.params.param('timefreq')
        
        # we take sampling_rate = f_stop*4 or (original sampling_rate)
        if tfr_params['f_stop']*4 < self.sampling_rate:
            sub_sampling_rate = tfr_params['f_stop']*4
        else:
            sub_sampling_rate = self.sampling_rate
        
        # this try to find the best size to get a timefreq of 2**N by changing
        # the sub_sampling_rate and the sig_chunk_size
        self.wanted_size = self.params['xsize']
        self.len_wavelet = l = int(2**np.ceil(np.log(self.wanted_size*sub_sampling_rate)/np.log(2)))
        self.sig_chunk_size = self.wanted_size*self.sampling_rate
        self.downsampling_factor = int(np.ceil(self.sig_chunk_size/l))
        self.sig_chunk_size = self.downsampling_factor*l
        self.sub_sampling_rate  = self.sampling_rate/self.downsampling_factor
        self.plot_length =  int(self.wanted_size*sub_sampling_rate)
        
        self.wavelet_fourrier = generate_wavelet_fourier(self.len_wavelet, tfr_params['f_start'], tfr_params['f_stop'],
                            tfr_params['deltafreq'], self.sub_sampling_rate, tfr_params['f0'], tfr_params['normalisation'])
        
        if self.downsampling_factor>1:
            self.filter_b = scipy.signal.firwin(9, 1. / self.downsampling_factor, window='hamming')
            self.filter_a = np.array([1.])
        else:
            self.filter_b = None
            self.filter_a = None
        
        for worker in self.workers:
            worker.on_fly_change_wavelet(wavelet_fourrier=self.wavelet_fourrier, downsampling_factor=self.downsampling_factor,
                        sig_chunk_size = self.sig_chunk_size, plot_length=self.plot_length, filter_a=self.filter_a, filter_b=self.filter_b)
        
        for input_map in self.input_maps:
            input_map.params['shape'] = (self.plot_length, self.wavelet_fourrier.shape[1])
            input_map.params['sampling_rate'] = sub_sampling_rate
    
    def initialize_plots(self):
        #TODO get cmap from somewhere esle
        from matplotlib.cm import get_cmap
        from matplotlib.colors import ColorConverter
        
        lut = [ ]
        cmap = get_cmap(self.params['colormap'] , 3000)
        for i in range(3000):
            r,g,b =  ColorConverter().to_rgb(cmap(i) )
            lut.append([r*255,g*255,b*255])
        self.lut = np.array(lut, dtype = np.uint8)
        
        tfr_params = self.params.param('timefreq')
        for i in range(self.nb_channel):
            print('initialize_plots', i)
            if self.by_channel_params.children()[i]['visible']:
                for item in self.plots[i].items:
                    #~ #remove old images
                    self.plots[i].removeItem(item)
                
                clim = self.by_channel_params.children()[i]['clim']
                f_start, f_stop = tfr_params['f_start'], tfr_params['f_stop']
                
                image = pg.ImageItem()
                image.setImage(np.zeros((self.plot_length,self.wavelet_fourrier.shape[1])), lut = self.lut, levels = [0,clim])
                self.plots[i].addItem(image)
                image.setRect(QtCore.QRectF(-self.wanted_size, f_start,self.wanted_size, f_stop-f_start))
                self.plots[i].setXRange( -self.wanted_size, 0.)
                self.plots[i].setYRange(f_start, f_stop)
                self.images[i] =image
        print('initialize_plots', 'done')
    
    
    def stop_workers(self):
        pass
        #~ for i in range(self.nb_channel):
            #~ if self.workers[i].running():
                #~ self.workers[i].stop()

    def start_workers(self):
        pass
        #~ for i in range(self.nb_channel):
            #~ if self.by_channel_params.children()[i]['visible']:
                #~ self.workers[i].start()
    
    def on_param_change(self, params, changes):
        for param, change, data in changes:
            if change != 'value': continue
            #immediate action
            if param.name()=='background_color':
                color = data
                for graphicsview in self.graphicsviews:
                    if graphicsview is not None:
                        graphicsview.setBackground(color)
            if param.name()=='refresh_interval':
                self.global_timer.setInterval(data)
            if param.name()=='clim':
                i = self.by_channel_params.children().index(param.parent())
                clim = param.value()
                if self.images[i] is not None:
                    self.images[i].setImage(self.images[i].image, lut = self.lut, levels = [0,clim])
            
            with self.mutex_action:
                #difered action
                if param.name()=='xsize':
                    self.actions[self.initialize_time_freq] = True
                    self.actions[self.initialize_plots] = True
                if param.name()=='colormap':
                    self.actions[self.initialize_plots] = True
                if param.name()=='nb_column':
                    self.actions[self.create_grid] = True
                    self.actions[self.initialize_plots] = True
                if param.name() in ('f_start', 'f_stop', 'deltafreq', 'f0', 'normalisation'):
                    self.actions[self.initialize_time_freq] = True
                    self.actions[self.initialize_plots] = True
                if param.name()=='visible':
                    self.actions[self.create_grid] = True
                    self.actions[self.initialize_plots] = True
        
        with self.mutex_action:
            if not self.timer_action.isActive() and any(self.actions.values()):
                self.timer_action.start()
    
    def apply_actions(self):
        with self.mutex_action:
            if self.running():
                self.global_timer.stop()
                #~ print('stop_workers')
                #~ self.stop_workers
            for action, flag in self.actions.items():
                print(action, flag)
                if flag:
                    action()
                    print('done')
            for action in self.actions:
                self.actions[action] = False
            
            if self.running():
                self.global_timer.start()
                #~ print('start_workers')
                #~ self.start_workers
    
    def compute_maps(self):
        head = self.global_poller.pos()
        for i in range(self.nb_channel):
            if self.by_channel_params.children()[i]['visible']:
                if self.local_workers:
                    self.workers[i].compute_one_map(head)
                else:
                    self.workers[i].compute_one_map(int(head), _sync = False)
    
    def on_new_map_local(self, i):
        _, wt_map = self.input_maps[i].recv()
        #~ print('on_new_map_local', 'wt_map', i, wt_map.shape)
        if self.images[i] is None: return
        self.images[i].updateImage(wt_map)
    
    def on_new_map_socket(self, pos, wt_map):
        i = self.sender().i
        if self.images[i] is None: return
        self.images[i].updateImage(wt_map)

    def clim_zoom(self, factor):
        for i, p in enumerate(self.by_channel_params.children()):
            p.param('clim').setValue(p.param('clim').value()*factor)
        
    def xsize_zoom(self, xmove):
        factor = xmove/100.
        newsize = self.params['xsize']*(factor+1.)
        limits = self.params.param('xsize').opts['limits']
        if newsize>limits[0] and newsize<limits[1]:
            self.params['xsize'] = newsize    

    def auto_clim(self, identic = True):
        if identic:
            all = [ ]
            for i, p in enumerate(self.by_channel_params.children()):
                if p.param('visible').value():
                    all.append(np.max(self.images[i].image))
            clim = np.max(all)*1.1
            for i, p in enumerate(self.by_channel_params.children()):
                if p.param('visible').value():
                    p.param('clim').setValue(float(clim))
        else:
            for i, p in enumerate(self.by_channel_params.children()):
                if p.param('visible').value():
                    clim = np.max(self.images[i].image)*1.1
                    p.param('clim').setValue(float(clim))

register_node_type(QTimeFreq)


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
        Frequency interval in Hznew_head
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



class ComputeThread(QtCore.QThread):
    def __init__(self, in_stream, out_stream, channel, local, parent=None):
        QtCore.QThread.__init__(self, parent)
        self.in_stream = weakref.ref(in_stream)
        self.out_stream = weakref.ref(out_stream)
        self.channel = channel
        self.local = local
        
        self.worker_params = None

    def run(self):
        if self.worker_params is None: 
            return
        head = self.head
        
        for k, v in self.worker_params.items():
            setattr(self, k, v)
        
        t1 = time.time()
        
        if self.downsampling_factor>1:
            head = head - head%self.downsampling_factor
        full_arr = self.in_stream().get_array_slice(head, self.sig_chunk_size)[self.channel, :]
        
        t2 = time.time()
        
        if self.downsampling_factor>1:
            small_arr = scipy.signal.filtfilt(self.filter_b, self.filter_a, full_arr)
            small_arr =small_arr[::self.downsampling_factor].copy()# to ensure continuity
        else:
            small_arr = full_arr
        
        small_arr_f=scipy.fftpack.fft(small_arr)
        #~ print(small_arr_f.shape[0], self.wavelet_fourrier.shape[0])
        if small_arr_f.shape[0] != self.wavelet_fourrier.shape[0]: return
        wt_tmp=scipy.fftpack.ifft(small_arr_f[:,np.newaxis]*self.wavelet_fourrier,axis=0)
        wt = scipy.fftpack.fftshift(wt_tmp,axes=[0])
        wt = np.abs(wt).astype('float32')
        wt = wt[-self.plot_length:]
        
        #~ wt = np.random.randn(*self.wavelet_fourrier.shape).astype(self.out_stream().params['dtype'])
        #~ wt = wt[-self.plot_length:]
        #send map
        #~ self._n += 1
        if self.local:
            self.last_wt_map = wt
            #~ self.wt_map_done.emit(self.channel)
            self.out_stream().send(0, wt)
        else:
            self.out_stream().send(0, wt)
        t3 = time.time()
        
        print('compute', self.channel,  t2-t1, t3-t2, t3-t1, QtCore.QThread.currentThreadId())



class TimeFreqWorker(Node):
    _input_specs = {'signal' : dict(streamtype = 'signals', transfermode = 'sharedarray', timeaxis=1, ring_buffer_method = 'double')}
    _output_specs = {'timefreq' : dict(streamtype = 'image', dtype = 'float32')}
    
    #~ sig_on_fly_change_wavelet = QtCore.pyqtSignal(object)
    #~ sig_set_interval = QtCore.pyqtSignal(int)
    wt_map_done = QtCore.pyqtSignal(int)
    def __init__(self, **kargs):
        Node.__init__(self, **kargs)
        assert HAVE_SCIPY, "TimeFreqWorker node depends on the `scipy` package, but it could not be imported."
    
    def _configure(self, max_xsize = 60., channel = None, local = True):
        self.max_xsize = max_xsize
        self.channel = channel
        self.local = local
    
    def after_input_connect(self, inputname):
        assert len(self.input.params['shape']) == 2, 'Wrong shape: TimeFreqWorker'
        assert self.input.params['timeaxis'] == 1, 'Wrong timeaxis: TimeFreqWorker'
        assert self.input.params['transfermode'] == 'sharedarray', 'Wrong shape: sharedarray'
        
        
    def _initialize(self):
        self.sampling_rate = sr = self.input.params['sampling_rate']
        self.thread = ComputeThread(self.input, self.output, self.channel, self.local)
        self.thread.finished.connect(self.on_thread_done)
        
        #~ if not self.local:
            #~ self.poller = ThreadPollInput(input_stream = self.input)
            #~ self.poller.new_data.connect(self.back_compute.new_head)

        #~ self.poller = ThreadPollInput(input_stream = self.input)
        #~ self.poller.new_data.connect(self.back_compute.new_head)


    def _start(self):
        pass
        #~ self.thread.start()
        #~ if not self.local:
            #~ self.poller.start()
        #~ self.poller.start()
    
    def _stop(self):
        pass
        #~ self.thread.exit()
        #~ self.thread.wait()
        #~ if not self.local:
            #~ self.poller.stop()
            #~ self.poller.wait()
        #~ self.poller.stop()
        #~ self.poller.wait()
    
    def _close(self):
        if self.running():
            self.stop()
    
    #~ def on_fly_change_wavelet(self, wavelet_fourrier=None, downsampling_factor=None, sig_chunk_size = None,
            #~ plot_length=None, filter_a=None, filter_b=None):
    def on_fly_change_wavelet(self, **worker_params):
        p = self.worker_params = worker_params
        p['out_shape'] = (p['plot_length'], p['wavelet_fourrier'].shape[1])
        self.output.params['shape'] = p['out_shape']
        self.output.params['sampling_rate'] = self.sampling_rate/p['downsampling_factor']
    
    def on_thread_done(self):
        self.thread.wait()
        self.wt_map_done.emit(self.channel)
        print('done', self.channel)
    
    def compute_one_map(self, head):
        if self.thread.isRunning():
            return
        #~ print(self.worker_params)
        self.thread.worker_params = self.worker_params
        self.thread.head = head
        self.thread.start()
    
    def set_interval(self, interval):
        pass
        #~ self.sig_set_interval.emit(interval)

register_node_type(TimeFreqWorker)




class TimeFreqControler(QtGui.QWidget):
    def __init__(self, parent = None, viewer= None):
        QtGui.QWidget.__init__(self, parent)
        
        self._viewer = weakref.ref(viewer)
        
        #layout
        self.mainlayout = QtGui.QVBoxLayout()
        self.setLayout(self.mainlayout)
        t = 'Options for {}'.format(self.viewer.name)
        self.setWindowTitle(t)
        self.mainlayout.addWidget(QtGui.QLabel('<b>'+t+'<\b>'))
        
        h = QtGui.QHBoxLayout()
        self.mainlayout.addLayout(h)

        self.tree_params = pg.parametertree.ParameterTree()
        self.tree_params.setParameters(self.viewer.params, showTop=True)
        self.tree_params.header().hide()
        h.addWidget(self.tree_params)

        self.tree_by_channel_params = pg.parametertree.ParameterTree()
        self.tree_by_channel_params.header().hide()
        h.addWidget(self.tree_by_channel_params)
        self.tree_by_channel_params.setParameters(self.viewer.by_channel_params, showTop=True)

        v = QtGui.QVBoxLayout()
        h.addLayout(v)
        
        if self.viewer.nb_channel>1:
            v.addWidget(QtGui.QLabel('<b>Select channel...</b>'))
            names = [ p.name() for p in self.viewer.by_channel_params ]
            self.qlist = QtGui.QListWidget()
            v.addWidget(self.qlist, 2)
            self.qlist.addItems(names)
            self.qlist.setSelectionMode(QtGui.QAbstractItemView.ExtendedSelection)
            
            for i in range(len(names)):
                self.qlist.item(i).setSelected(True)            
            v.addWidget(QtGui.QLabel('<b>and apply...<\b>'))
        
        # 
        but = QtGui.QPushButton('set visble')
        v.addWidget(but)
        but.clicked.connect(self.on_set_visible)
        
        but = QtGui.QPushButton('Automatic clim (same for all)')
        but.clicked.connect(lambda: self.auto_clim( identic = True))
        v.addWidget(but)

        but = QtGui.QPushButton('Automatic clim (independant)')
        but.clicked.connect(lambda: self.auto_clim( identic = False))
        v.addWidget(but)
        
        v.addWidget(QtGui.QLabel(self.tr('<b>Clim change (mouse wheel on graph):</b>'),self))
        h = QtGui.QHBoxLayout()
        v.addLayout(h)
        for label, factor in [ ('--', 1./10.), ('-', 1./1.3), ('+', 1.3), ('++', 10.),]:
            but = QtGui.QPushButton(label)
            but.factor = factor
            but.clicked.connect(self.clim_zoom)
            h.addWidget(but)
    
    @property
    def viewer(self):
        return self._viewer()

    @property
    def selected(self):
        selected = np.ones(self.viewer.nb_channel, dtype = bool)
        if self.viewer.nb_channel>1:
            selected[:] = False
            selected[[ind.row() for ind in self.qlist.selectedIndexes()]] = True
        return selected
    
    def on_set_visible(self):
        # apply
        visibles = self.selected
        for i,param in enumerate(self.viewer.by_channel_params.children()):
            param['visible'] = visibles[i]

    def auto_clim(self, identic = True):
        self.viewer.auto_clim(identic=identic)

    def clim_zoom(self):
        factor = self.sender().factor
        for i, p in enumerate(self.viewer.by_channel_params.children()):
            p.param('clim').setValue(p.param('clim').value()*factor)

