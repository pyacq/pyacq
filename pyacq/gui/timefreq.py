# -*- coding: utf-8 -*-

from PyQt4 import QtCore,QtGui
import pyqtgraph as pg
import zmq

from .tools import RecvPosThread
from .guiutil import *
from .multichannelparam import MultiChannelParam

from matplotlib.cm import get_cmap
from matplotlib.colors import ColorConverter

from scipy import fftpack

param_global = [
    {'name': 'xsize', 'type': 'logfloat', 'value': 10., 'step': 0.1, 'limits' : (.1, 60)},
    {'name': 'nb_column', 'type': 'int', 'value': 1},
    {'name': 'background_color', 'type': 'color', 'value': 'k' },
    {'name': 'colormap', 'type': 'list', 'value': 'jet', 'values' : ['jet', 'gray', 'bone', 'cool', 'hot', ] },
    {'name': 'refresh_interval', 'type': 'int', 'value': 500 , 'limits':[5, 1000]},
    
    ]

param_timefreq = [ 
    {'name': 'f_start', 'type': 'float', 'value': 3., 'step': 1.},
    {'name': 'f_stop', 'type': 'float', 'value': 90., 'step': 1.},
    {'name': 'deltafreq', 'type': 'float', 'value': 3., 'step': 1.,  'limits' : (0.001, 1.e6)},
    {'name': 'f0', 'type': 'float', 'value': 2.5, 'step': 0.1},
    {'name': 'normalisation', 'type': 'float', 'value': 0., 'step': 0.1},
    ]

param_by_channel = [ 
                #~ {'name': 'channel_name', 'type': 'str', 'value': '','readonly' : True},
                #~ {'name': 'channel_index', 'type': 'str', 'value': '','readonly' : True},
                {'name': 'visible', 'type': 'bool', 'value': True},
                {'name': 'clim', 'type': 'float', 'value': 10.},
            ]



class MyViewBox(pg.ViewBox):
    doubleclicked = QtCore.pyqtSignal()
    zoom = QtCore.pyqtSignal(float)
    def __init__(self, *args, **kwds):
        pg.ViewBox.__init__(self, *args, **kwds)
    def mouseClickEvent(self, ev):
        ev.accept()
    def mouseDoubleClickEvent(self, ev):
        self.doubleclicked.emit()
        ev.accept()
    def mouseDragEvent(self, ev):
        ev.ignore()
    def wheelEvent(self, ev):
        if ev.modifiers() ==  Qt.ControlModifier:
            z = 10 if ev.delta()>0 else 1/10.
        else:
            z = 1.3 if ev.delta()>0 else 1/1.3
        self.zoom.emit(z)
        ev.accept()

class TimeFreq(QtGui.QWidget):
    def __init__(self, stream = None, parent = None,
                            max_visible_on_open = 4,):
        QtGui.QWidget.__init__(self, parent)
        
        assert stream['type'] == 'signals_stream_sharedmem'
        
        self.stream = stream
        
        self.mainlayout = QtGui.QVBoxLayout()
        self.setLayout(self.mainlayout)

        self.grid = QtGui.QGridLayout()
        self.mainlayout.addLayout(self.grid)
        
        
        
        # Create parameters
        n = stream['nb_channel']
        self.np_array = self.stream['shared_array'].to_numpy_array()
        self.half_size = self.np_array.shape[1]/2
        sr = self.stream['sampling_rate']
        
        self.paramGlobal = pg.parametertree.Parameter.create( name='Global options', type='group',
                                                    children =param_global)
        nb_column = np.rint(np.sqrt(max_visible_on_open))
        self.paramGlobal.param('nb_column').setValue(nb_column)
        
        self.paramTimeFreq = pg.parametertree.Parameter.create( name='Time frequency options', 
                                                    type='group', children = param_timefreq)
        
        all = [ ]
        for i, channel_index, channel_name in zip(range(n), stream['channel_indexes'], stream['channel_names']):
            name = 'Signal{} name={} channel_index={}'.format(i, channel_name,channel_index)
            all.append({ 'name': name, 'type' : 'group', 'children' : param_by_channel})
        self.paramChannels = pg.parametertree.Parameter.create(name='AnalogSignals', type='group', children=all)
        for p in self.paramChannels.children()[max_visible_on_open:]:
            p.param('visible').setValue(False)
        
        self.allParams = pg.parametertree.Parameter.create(name = 'all param', type = 'group', 
                                                        children = [self.paramGlobal,self.paramChannels, self.paramTimeFreq  ])
        
        self.paramControler = TimefreqControler(parent = self)
        self.paramControler.setWindowFlags(Qt.Window)
        
        self.graphicsviews = [ ]
        self.grid_changing =False
        self.create_grid()
        
        self.thread_initialize_tfr = None
        self.need_recreate_thread = True
        
        self.initialize_time_freq()
        self.initialize_tfr_finished.connect(self.refresh)

        # this signal is used when trying to change many time tfr params
        self.timer_back_initialize = QTimer(singleShot = True, interval = 300)
        self.timer_back_initialize.timeout.connect(self.initialize_time_freq)
        
        # this signal is a hack when many signal are emited at the same time
        # only the first is taken
        self.need_change_grid.connect(self.do_change_grid, type = Qt.QueuedConnection)


        self.paramGlobal.sigTreeStateChanged.connect(self.on_param_change)
        self.paramTimeFreq.sigTreeStateChanged.connect(self.initialize_time_freq)
        for p in self.paramChannels.children():
            p.param('visible').sigValueChanged.connect(self.change_grid)
            p.param('clim').sigValueChanged.connect(self.clim_changed)

        self.context = zmq.Context()
        self.socket = self.context.socket(zmq.SUB)
        self.socket.setsockopt(zmq.SUBSCRIBE,'')
        self.socket.connect("tcp://localhost:{}".format(self.stream['port']))

        self.thread_pos = RecvPosThread(socket = self.socket, port = self.stream['port'])
        self.thread_pos.start()

        self.timer = QtCore.QTimer(interval = 500)
        self.timer.timeout.connect(self.refresh)
        self.timer.start()
        
        #~ self.paramGlobal.param('xsize').setValue(3)

    def change_param_channel(self, channel, **kargs):
        p  = self.paramChannels.children()[channel]
        for k, v in kargs.items():
            p.param(k).setValue(v)
        
    def change_param_global(self, **kargs):
        for k, v in kargs.items():
            self.paramGlobal.param(k).setValue(v)

    def change_param_tfr(self, **kargs):
        for k, v in kargs.items():
            self.paramTimeFreq.param(k).setValue(v)

    def on_param_change(self, params, changes):
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
                self.self.change_grid()
            if param.name()=='refresh_interval':
                self.timer.setInterval(data)
       

    need_change_grid = pyqtSignal()
    def change_grid(self, param):
        if not self.grid_changing:
            self.need_change_grid.emit()
        
    def do_change_grid(self):
        self.grid_changing = True
        self.create_grid()
        self.initialize_time_freq()
        self.initialize_tfr_finished.connect(self.grid_changed_done)
        
    def grid_changed_done(self):
        self.initialize_tfr_finished.disconnect(self.grid_changed_done)
        self.grid_changing = False
        
    def clim_changed(self, param):
        i = self.paramChannels.children().index( param.parent())
        clim = param.value()
        if self.images[i] is not None:
            self.images[i].setImage(self.maps[i], lut = self.jet_lut, levels = [0,clim])
        
    def open_configure_dialog(self):
        self.paramControler.show()
        
    def create_grid(self):
        color = self.paramGlobal.param('background_color').value()
        #~ self.graphicsview.setBackground(color)

        
        n = self.stream['nb_channel']
        for graphicsview in self.graphicsviews:
            if graphicsview is not None:
                graphicsview.hide()
                self.grid.removeWidget(graphicsview)
        self.plots =  [ None for i in range(n)]
        self.graphicsviews =  [ None for i in range(n)]
        r,c = 0,0
        for i in range(self.stream['nb_channel']):
            if not self.paramChannels.children()[i].param('visible').value(): continue

            viewBox = MyViewBox()
            viewBox.doubleclicked.connect(self.open_configure_dialog)
            viewBox.zoom.connect(self.paramControler.clim_zoom)
            
            graphicsview  = pg.GraphicsView()#useOpenGL = True)
            graphicsview.setBackground(color)
            plot = pg.PlotItem(viewBox = viewBox)
            graphicsview.setCentralItem(plot)
            self.graphicsviews[i] = graphicsview
            
            self.plots[i] = plot
            self.grid.addWidget(graphicsview, r,c)
            
            c+=1
            if c==self.paramGlobal.param('nb_column').value():
                c=0
                r+=1
        self.images = [ None for i in range(n)]
        self.maps = [ None for i in range(n)]
        self.is_computing = np.zeros((n), dtype = bool)
        self.threads = [ None for i in range(n)]
        
    initialize_tfr_finished = QtCore.pyqtSignal()
    def initialize_time_freq(self):
        if self.thread_initialize_tfr is not None or self.is_computing.any():
            # needd to come back later ...
            if not self.timer_back_initialize.isActive():
                self.timer_back_initialize.start()
            return
        # create self.params_time_freq
        p = self.params_time_freq = { }
        for param in self.paramTimeFreq.children():
            self.params_time_freq[param.name()] = param.value()
        
        
        # we take sampling_rate = f_stop*4 or (original sampling_rate)
        #~ if p['f_stop']*4 < self.stream['sampling_rate']:
        if p['f_stop']*4 < self.stream['sampling_rate']:
            p['sampling_rate'] = p['f_stop']*4
        else:
            p['sampling_rate']  = self.stream['sampling_rate']
        self.factor = p['sampling_rate']/self.stream['sampling_rate'] # this compensate unddersampling in FFT.
        
        self.xsize2 = self.paramGlobal.param('xsize').value()
        self.len_wavelet = int(self.xsize2*p['sampling_rate'])
        self.win = fftpack.ifftshift(np.hamming(self.len_wavelet))
        self.thread_initialize_tfr = ThreadInitializeWavelet(len_wavelet = self.len_wavelet, 
                                                            params_time_freq = p, parent = self )
        self.thread_initialize_tfr.finished.connect(self.initialize_tfr_done)
        self.thread_initialize_tfr.start()
        
    
    def initialize_tfr_done(self):
        colormap = self.paramGlobal.param('colormap').value()
        lut = [ ]
        cmap = get_cmap(colormap , 10000)
        for i in range(10000):
            r,g,b =  ColorConverter().to_rgb(cmap(i) )
            lut.append([r*255,g*255,b*255])
        self.jet_lut = np.array(lut, dtype = np.uint8)


        
        self.wf = self.thread_initialize_tfr.wf
        p = self.params_time_freq
        for i in range(self.stream['nb_channel']):
            if not self.paramChannels.children()[i].param('visible').value(): continue
            plot = self.plots[i]
            self.maps[i] = np.zeros(self.wf.shape)
            if self.images[i] is not None:# for what ???
                plot.removeItem(self.images[i])# for what ???
            image = pg.ImageItem()
            plot.addItem(image)
            plot.setYRange(p['f_start'], p['f_stop'])
            self.images[i] =image
            clim = self.paramChannels.children()[i].param('clim').value()
            self.images[i].setImage(self.maps[i], lut = self.jet_lut, levels = [0,clim])
            
            #~ self.t_start, self.t_stop = self.t-self.xsize2/3. , self.t+self.xsize2*2./3.
            f_start, f_stop = p['f_start'], p['f_stop']
            image.setRect(QRectF(-self.xsize2, f_start,self.xsize2, f_stop-f_start))

        self.sig_chunk_size = int(np.rint(self.xsize2*self.stream['sampling_rate']))
        self.empty_sigs = [np.zeros(self.sig_chunk_size, dtype = self.np_array.dtype) for i in range(self.stream['nb_channel'])]
        
        self.freqs = np.arange(p['f_start'],p['f_stop'],p['deltafreq'])
        self.need_recreate_thread = True
        
        self.thread_initialize_tfr = None
        self.initialize_tfr_finished.emit()
    
    
    def refresh(self):
        if self.thread_initialize_tfr is not None or self.is_computing.any():
            return
        if self.timer_back_initialize.isActive():
            return
        if self.thread_pos.pos is None: return
        head = self.thread_pos.pos%self.half_size+self.half_size
        tail = head-self.sig_chunk_size
        np_arr = self.np_array[:,tail:head]

        
        #~ self.t_start, self.t_stop = self.t-self.xsize2/3. , self.t+self.xsize2*2./3.

        for i in range(self.stream['nb_channel']):
            if not self.paramChannels.children()[i].param('visible').value(): continue
            if self.need_recreate_thread:
                    self.threads[i] = ThreadComputeTF(None, self.wf, self.win,i, self.factor, parent = self)
                    self.threads[i].finished.connect(self.map_computed)
            self.is_computing[i] = True
            self.threads[i].sig = np_arr[i,:]
            
            self.plots[i].setXRange( -self.xsize2, 0.)
            
            f_start, f_stop = self.params_time_freq['f_start'], self.params_time_freq['f_stop']
            self.images[i].setRect(QRectF(-self.xsize2, f_start,self.xsize2, f_stop-f_start))
            self.threads[i].start()
        
        self.need_recreate_thread = False
        self.is_refreshing = False

    def map_computed(self, i):
        if self.sender() is not self.threads[i]:# thread have changes
            self.is_computing[i] = False
            return
        if not self.grid_changing and self.thread_initialize_tfr is None:
            if self.images[i] is not None:
                self.images[i].updateImage(self.maps[i])
        self.is_computing[i] = False



class ThreadComputeTF(QtCore.QThread):
    finished = QtCore.pyqtSignal(int)
    def __init__(self, sig, wf, win,n, factor, parent = None, ):
        QtCore.QThread.__init__(self, parent)
        self.sig = sig
        self.wf = wf
        self.win = win
        self.n = n
        self.factor = factor # this compensate subsampling
        
    def run(self):
        sigf=fftpack.fft(self.sig)
        n = self.wf.shape[0]
        sigf = np.concatenate([sigf[0:(n+1)/2],  sigf[-(n-1)/2:]])*self.factor
        #~ sigf *= self.win
        wt_tmp=fftpack.ifft(sigf[:,np.newaxis]*self.wf,axis=0)
        wt = fftpack.fftshift(wt_tmp,axes=[0])
        
        self.parent().maps[self.n] = np.abs(wt)
        self.finished.emit(self.n)

def generate_wavelet_fourier(len_wavelet,
            f_start,
            f_stop,
            deltafreq,
            sampling_rate,
            f0,
            normalisation,
            ):
    """
    Compute the wavelet coefficients at all scales and makes its Fourier transform.
    When different signal scalograms are computed with the exact same coefficients, 
        this function can be executed only once and its result passed directly to compute_morlet_scalogram
        
    Output:
        wf : Fourier transform of the wavelet coefficients (after weighting), Fourier frequencies are the first 
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
    #~ wf=fft(wavelet_coefs.conj(),axis=0) <- FALSE
    wf=fftpack.fft(wavelet_coefs,axis=0)
    wf=wf.conj() # at this point there was a mistake in the original script
    
    return wf

class ThreadInitializeWavelet(QtCore.QThread):
    finished = QtCore.pyqtSignal()
    def __init__(self, len_wavelet = None, params_time_freq = {}, parent = None, ):
        QtCore.QThread.__init__(self, parent)
        self.len_wavelet = len_wavelet
        self.params_time_freq = params_time_freq
        
    def run(self):
        self.wf = generate_wavelet_fourier(len_wavelet= self.len_wavelet, ** self.params_time_freq)
        self.finished.emit()
        
        
        
class TimefreqControler(QtGui.QWidget):
    def __init__(self, parent = None):
        QtGui.QWidget.__init__(self, parent)

        self.viewer = parent

        #layout
        self.mainlayout = QtGui.QVBoxLayout()
        self.setLayout(self.mainlayout)
        t = u'Options for AnalogSignals'
        self.setWindowTitle(t)
        self.mainlayout.addWidget(QLabel('<b>'+t+'<\b>'))
        
        h = QtGui.QHBoxLayout()
        self.mainlayout.addLayout(h)

        v = QtGui.QVBoxLayout()
        h.addLayout(v)
        
        self.treeParamGlobal = pg.parametertree.ParameterTree()
        self.treeParamGlobal.header().hide()
        v.addWidget(self.treeParamGlobal)
        self.treeParamGlobal.setParameters(self.viewer.paramGlobal, showTop=True)
        
        self.treeParamTimeFreq = pg.parametertree.ParameterTree()
        self.treeParamTimeFreq.header().hide()
        v.addWidget(self.treeParamTimeFreq)
        self.treeParamTimeFreq.setParameters(self.viewer.paramTimeFreq, showTop=True)
        
        v.addWidget(QLabel(self.tr('<b>Automatic color scale:<\b>'),self))
        but = QtGui.QPushButton('Identic')
        but.clicked.connect(lambda: self.auto_clim( identic = True))
        v.addWidget(but)
        but = QtGui.QPushButton('Independent')
        but.clicked.connect(lambda: self.auto_clim( identic = False))
        v.addWidget(but)
        
        h2 = QtGui.QHBoxLayout()
        v.addLayout(h2)
        but = QtGui.QPushButton('-')
        but.clicked.connect(lambda : self.clim_zoom(.8))
        h2.addWidget(but)
        but = QtGui.QPushButton('+')
        but.clicked.connect(lambda : self.clim_zoom(1.2))
        h2.addWidget(but)        
        
        self.treeParamSignal = pg.parametertree.ParameterTree()
        self.treeParamSignal.header().hide()
        h.addWidget(self.treeParamSignal)
        self.treeParamSignal.setParameters(self.viewer.paramChannels, showTop=True)
        
        if self.viewer.stream['nb_channel']>1:
            self.multi = MultiChannelParam( all_params = self.viewer.paramChannels, param_by_channel = param_by_channel)
            h.addWidget(self.multi)

    def auto_clim(self, identic = True):
        
        if identic:
            all = [ ]
            for i, p in enumerate(self.viewer.paramChannels.children()):
                if p.param('visible').value():
                    all.append(np.max(self.viewer.maps[i]))
            clim = np.max(all)*1.1
            for i, p in enumerate(self.viewer.paramChannels.children()):
                if p.param('visible').value():
                    p.param('clim').setValue(clim)
        else:
            for i, p in enumerate(self.viewer.paramChannels.children()):
                if p.param('visible').value():
                    clim = np.max(self.viewer.maps[i])*1.1
                    p.param('clim').setValue(clim)
    
    def clim_zoom(self, factor):
        for i, p in enumerate(self.viewer.paramChannels.children()):
            p.param('clim').setValue(p.param('clim').value()*factor)

        
        
        


