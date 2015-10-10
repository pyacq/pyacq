from pyqtgraph.Qt import QtCore, QtGui
import pyqtgraph as pg

import numpy as np
import weakref

from ..core import (WidgetNode, register_node_type, InputStream,
        ThreadPollInput, StreamConverter)


class MyViewBox(pg.ViewBox):
    doubleclicked = QtCore.pyqtSignal()
    gain_zoom = QtCore.pyqtSignal(float)
    xsize_zoom = QtCore.pyqtSignal(float)
    def __init__(self, *args, **kwds):
        pg.ViewBox.__init__(self, *args, **kwds)
        self.disableAutoRange()
    def mouseClickEvent(self, ev):
        ev.accept()
    def mouseDoubleClickEvent(self, ev):
        self.doubleclicked.emit()
        ev.accept()
    def mouseDragEvent(self, ev):
        ev.ignore()
    def wheelEvent(self, ev):
        if ev.modifiers() == QtCore.Qt.ControlModifier:
            z = 10 if ev.delta()>0 else 1/10.
        else:
            z = 1.3 if ev.delta()>0 else 1/1.3
        self.gain_zoom.emit(z)
        ev.accept()
    def mouseDragEvent(self, ev):
        ev.accept()
        self.xsize_zoom.emit((ev.pos()-ev.lastPos()).x())


class BaseOscilloscope(WidgetNode):
    """
    Base Class for QOscilloscope and QOscilloscopeDigital
    
    The BaseOscilloscope requires its input stream to have the following properties:
    
    * transfermode==sharedarray
    * timeaxis==1
    
    If the input stream does not meet these requirements, then a StreamConverter
    is created to proxy the input. This can degrade performance when multiple
    Oscilloscopes are used to view data from the same device; in this case it is
    better to manually create single StreamConverter to provide shared input
    for all Oscilloscopes.
    """
    def __init__(self, **kargs):
        WidgetNode.__init__(self, **kargs)
        
        self.layout = QtGui.QHBoxLayout()
        self.setLayout(self.layout)
        
        self.graphicsview = pg.GraphicsView()
        self.layout.addWidget(self.graphicsview)
        
        # create graphic view and plot item
        self.viewBox = MyViewBox()
        
        self.plot = pg.PlotItem(viewBox=self.viewBox)
        self.graphicsview.setCentralItem(self.plot)
        self.plot.hideButtons()
        self.plot.showAxis('left', False)
        self.plot.showAxis('bottom', False)
        
        self.all_mean, self.all_sd = None, None
        
    def show_params_controler(self):
        self.params_controler.show()
        # TODO deal with modality
    
    def _configure(self, with_user_dialog=True, max_xsize=60.):
        self.with_user_dialog = with_user_dialog
        self.max_xsize = max_xsize
    
    def _initialize(self):
        assert len(self.input.params['shape']) == 2, 'Are you joking ?'
        d0, d1 = self.input.params['shape']
        if self.input.params['timeaxis']==0:
            self.nb_channel = d1
        else:
            self.nb_channel = d0
        
        sr = self.input.params['sample_rate']
        # create proxy input
        if self.input.params['transfermode'] == 'sharedarray' and self.input.params['timeaxis'] == 1:
            self.proxy_input = self.input
            self.conv = None
        else:
            # if input is not transfermode creat a proxy
            self.conv = StreamConverter()
            self.conv.configure()
            self.conv.input.connect(self.input.params)
            if self.input.params['timeaxis']==0:
                new_shape = (d1, d0)
            else:
                new_shape = (d0, d1)
            self.conv.output.configure(protocol='inproc', interface='127.0.0.1', port='*', 
                   transfermode='sharedarray', streamtype='analogsignal',
                   dtype='float32', shape=new_shape, timeaxis=1, 
                   compression='', scale=None, offset=None, units='',
                   sharedarray_shape=(self.nb_channel, int(sr*self.max_xsize)), ring_buffer_method = 'double',
                   )
            self.conv.initialize()
            self.proxy_input = InputStream()
            self.proxy_input.connect(self.conv.output)
            

        # Create parameters
        all = []
        for i in range(self.nb_channel):
            name = 'Signal{}'.format(i)
            all.append({'name': name, 'type': 'group', 'children': self._default_by_channel_params})
        self.by_channel_params = pg.parametertree.Parameter.create(name='AnalogSignals', type='group', children=all)
        self.params = pg.parametertree.Parameter.create(name='Global options',
                                                    type='group', children=self._default_params)
        self.all_params = pg.parametertree.Parameter.create(name='all param',
                                    type='group', children=[self.params,self.by_channel_params])
        self.all_params.sigTreeStateChanged.connect(self.on_param_change)
        self.params.param('xsize').setLimits([2./sr, self.max_xsize*.95])
        
        if self.with_user_dialog:
            self.params_controler = OscilloscopeControler(parent=self, viewer=self)
            self.params_controler.setWindowFlags(QtCore.Qt.Window)
            self.viewBox.doubleclicked.connect(self.show_params_controler)
        else:
            self.params_controler = None
        
        
        # poller
        self.poller = ThreadPollInput(input_stream=self.proxy_input)
        self.poller.new_data.connect(self._on_new_data)
        # timer
        self._head = 0
        self.timer = QtCore.QTimer(singleShot=False, interval=100)
        self.timer.timeout.connect(self.refresh)

    def _start(self):
        self.estimate_decimate()
        self.reset_curves_data()
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
        if self.with_user_dialog:
            self.params_controler.close()

    def _on_new_data(self, pos, data):
        self._head = pos
    
    def refresh(self):
        self._refresh()

    def on_param_change(self, params, changes):
        for param, change, data in changes:
            if change != 'value': continue
            if param.name()=='visible':
                c = self.by_channel_params.children().index(param.parent())
                if data:
                    self.curves[c].show()
                else:
                    self.curves[c].hide()
            if param.name()=='background_color':
                self.graphicsview.setBackground(data)
            if param.name()=='xsize':
                if self.params['auto_decimate']:
                    self.estimate_decimate()
                self.reset_curves_data()
            if param.name()=='decimate':
                self.reset_curves_data()
            if param.name()=='auto_decimate':
                if data:
                    self.estimate_decimate()
                self.reset_curves_data()
            if param.name()=='refresh_interval':
                self.timer.setInterval(data)
            if param.name()=='mode':
                self.reset_curves_data()

    def reset_curves_data(self):
        xsize = self.params['xsize']
        decimate = self.params['decimate']
        sr = self.input.params['sample_rate']
        self.full_size = int(xsize*sr)
        self.small_size = self.full_size//decimate
        if self.small_size%2!=0:  # ensure for min_max decimate
            self.small_size -=1
        self.full_size = self.small_size*decimate
        self.t_vect = np.arange(0,self.small_size, dtype=float)/(sr/decimate)
        self.t_vect -= self.t_vect[-1]
        self.curves_data = [np.zeros((self.small_size), dtype=float) for i in range(self.nb_channel)]

    def estimate_decimate(self, nb_point=4000):
        xsize = self.params['xsize']
        sr = self.input.params['sample_rate']
        self.params['decimate'] = max(int(xsize*sr)//nb_point, 1)

    def xsize_zoom(self, xmove):
        factor = xmove/100.
        newsize = self.params['xsize']*(factor+1.)
        limits = self.params.param('xsize').opts['limits']
        if newsize>limits[0] and newsize<limits[1]:
            self.params['xsize'] = newsize


default_params = [
    {'name': 'xsize', 'type': 'float', 'value': 3., 'step': 0.1},
    {'name': 'ylim_max', 'type': 'float', 'value': 10.},
    {'name': 'ylim_min', 'type': 'float', 'value': -10.},
    {'name': 'background_color', 'type': 'color', 'value': 'k'},
    {'name': 'refresh_interval', 'type': 'int', 'value': 100, 'limits':[5, 1000]},
    {'name': 'mode', 'type': 'list', 'value': 'scroll', 'values': ['scan', 'scroll']},
    {'name': 'auto_decimate', 'type': 'bool', 'value': True},
    {'name': 'decimate', 'type': 'int', 'value': 1, 'limits': [1, None], },
    {'name': 'decimation_method', 'type': 'list', 'value': 'pure_decimate', 'values': ['pure_decimate', 'min_max', 'mean']},
    {'name': 'display_labels', 'type': 'bool', 'value': False},
    ]

default_by_channel_params = [ 
    {'name': 'gain', 'type': 'float', 'value': 1, 'step': 0.1},
    {'name': 'offset', 'type': 'float', 'value': 0., 'step': 0.1},
    {'name': 'visible', 'type': 'bool', 'value': True},
    ]


class QOscilloscope(BaseOscilloscope):
    """
    Continuous, multi-channel oscilloscope based on Qt and pyqtgraph.
    """
    _input_specs = {'signals': dict(streamtype='signals')}
    
    _default_params = default_params
    _default_by_channel_params = default_by_channel_params
    
    def __init__(self, **kargs):
        BaseOscilloscope.__init__(self, **kargs)
        
        self.viewBox.gain_zoom.connect(self.gain_zoom)
        self.viewBox.xsize_zoom.connect(self.xsize_zoom)
        
    def _initialize(self):
        BaseOscilloscope._initialize(self)
        
        self.curves = []
        self.channel_labels = []
        for i in range(self.nb_channel):
            color = '#7FFF00'  # TODO
            curve = pg.PlotCurveItem(pen=color)
            self.plot.addItem(curve)
            self.curves.append(curve)
            label = pg.TextItem('TODO name{}'.format(i), color=color, anchor=(0.5, 0.5), border=None, fill=pg.mkColor((128,128,128, 200)))
            self.plot.addItem(label)
            self.channel_labels.append(label)
        
        self.reset_curves_data()
    
    def _refresh(self):
        mode = self.params['mode']
        decimate = int(self.params['decimate'])
        gains = np.array([p['gain'] for p in self.by_channel_params.children()])
        offsets = np.array([p['offset'] for p in self.by_channel_params.children()])
        visibles = np.array([p['visible'] for p in self.by_channel_params.children()], dtype=bool)
        sr = self.input.params['sample_rate']
        xsize = self.params['xsize'] 
        
        head = self._head
        if decimate>1:
            if self.params['decimation_method'] == 'min_max':
                head = head - head%(decimate*2)
            else:
                head = head - head%decimate
            
        full_arr = self.proxy_input.get_array_slice(head,self.full_size)
        if decimate>1:
            if self.params['decimation_method'] == 'pure_decimate':
                small_arr = full_arr[:,::decimate].copy()
            elif self.params['decimation_method'] == 'min_max':
                arr = full_arr.reshape(full_arr.shape[0], -1, decimate*2)
                small_arr = np.empty((full_arr.shape[0], self.small_size), dtype=full_arr.dtype)
                small_arr[:, ::2] = arr.max(axis=2)
                small_arr[:, 1::2] = arr.min(axis=2)
            elif self.params['decimation_method'] == 'mean':
                arr = full_arr.reshape(full_arr.shape[0], -1, decimate)
                small_arr = arr.mean(axis=2)
            else:
                raise(NotImplementedError)
        else:
            small_arr = full_arr.copy()
        
        # gain/offset
        small_arr[visibles, :] *= gains[visibles, None]
        small_arr[visibles, :] += offsets[visibles, None]
        
        if mode=='scroll':
            for c, visible in enumerate(visibles):
                if visible:
                    self.curves_data[c] = small_arr[c,:]
        elif mode =='scan':
            ind = (head//decimate)%self.small_size+1
            for c, visible in enumerate(visibles):
                if visible:
                    self.curves_data[c] = np.concatenate((small_arr[c,-ind:], small_arr[c,:-ind]))

        for c, visible in enumerate(visibles):
            if visible:
               self.curves[c].setData(self.t_vect, self.curves_data[c], antialias=False)
            
        self.plot.setXRange(self.t_vect[0], self.t_vect[-1])
        self.plot.setYRange(self.params['ylim_min'], self.params['ylim_max'])

        for c, visible in enumerate(visibles):
            label = self.channel_labels[c]
            if visible and self.params['display_labels']:
                if self.all_mean is not None:
                    label.setPos(-self.params['xsize'], self.all_mean[c]*gains[c]+offsets[c])
                else:
                    label.setPos(-self.params['xsize'], offsets[c])
                label.setVisible(True)
            else:
                label.setVisible(False)

    def gain_zoom(self, factor, selected=None):
        for i, p in enumerate(self.by_channel_params.children()):
            if selected is not None and not selected[i]: continue
            if self.all_mean is not None:
                p['offset'] = p['offset'] + self.all_mean[i]*p['gain'] - self.all_mean[i]*p['gain']*factor
            p['gain'] = p['gain']*factor
    
    
    def autoestimate_scales(self):
        if self._head is None:
            return None, None
        head = self._head
        sr = self.input.params['sample_rate']
        xsize = self.params['xsize'] 
        np_arr = self.proxy_input.get_array_slice(head,self.full_size)
        self.all_sd = np.std(np_arr, axis=1)
        # self.all_mean = np.mean(np_arr, axis = 1)
        self.all_mean = np.median(np_arr, axis=1)
        return self.all_mean, self.all_sd

    def auto_gain_and_offset(self, mode=0, visibles=None):
        """
        mode = 0, 1, 2
        """
        if visibles is None:
            visibles = np.ones(self.nb_channel, dtype=bool)
        
        n = np.sum(visibles)
        if n==0: return
        
        av, sd = self.autoestimate_scales()
        if av is None: return
        
        if mode==0:
            ylim_min, ylim_max = np.min(av[visibles]-3*sd[visibles]), np.max(av[visibles]+3*sd[visibles]) 
            gains = np.ones(self.nb_channel, dtype=float)
            offsets = np.zeros(self.nb_channel, dtype=float)
        elif mode in [1, 2]:
            ylim_min, ylim_max = -.5, n-.5 
            gains = np.ones(self.nb_channel, dtype=float)
            if mode==1 and max(sd[visibles])!=0:
                gains = np.ones(self.nb_channel, dtype=float) * 1./(6.*max(sd[visibles]))
            elif mode==2:
                gains[sd!=0] = 1./(6.*sd[sd!=0])
            offsets = np.zeros(self.nb_channel, dtype=float)
            offsets[visibles] = range(n)[::-1] - av[visibles]*gains[visibles]
        
        # apply
        for i,param in enumerate(self.by_channel_params.children()):
            param['gain'] = gains[i]
            param['offset'] = offsets[i]
            param['visible'] = visibles[i]
        self.params['ylim_min'] = ylim_min
        self.params['ylim_max'] = ylim_max


register_node_type(QOscilloscope)




class OscilloscopeControler(QtGui.QWidget):
    def __init__(self, parent=None, viewer=None):
        QtGui.QWidget.__init__(self, parent)
        
        self._viewer = weakref.ref(viewer)
        
        # layout
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
            names = [p.name() for p in self.viewer.by_channel_params]
            self.qlist = QtGui.QListWidget()
            v.addWidget(self.qlist, 2)
            self.qlist.addItems(names)
            self.qlist.setSelectionMode(QtGui.QAbstractItemView.ExtendedSelection)
            
            for i in range(len(names)):
                self.qlist.item(i).setSelected(True)            
            v.addWidget(QtGui.QLabel('<b>and apply...<\b>'))
             
            
            
        
        # Gain and offset
        but = QtGui.QPushButton('set visble')
        v.addWidget(but)
        but.clicked.connect(self.on_set_visible)
        
        for i,text in enumerate(['Real scale (gain = 1, offset = 0)',
                            'Fake scale (same gain for all)',
                            'Fake scale (gain per channel)',]):
            but = QtGui.QPushButton(text)
            v.addWidget(but)
            but.mode = i
            but.clicked.connect(self.on_auto_gain_and_offset)
        
        
        v.addWidget(QtGui.QLabel(self.tr('<b>Gain zoom (mouse wheel on graph):</b>'),self))
        h = QtGui.QHBoxLayout()
        v.addLayout(h)
        for label, factor in [('--', 1./10.), ('-', 1./1.3), ('+', 1.3), ('++', 10.),]:
            but = QtGui.QPushButton(label)
            but.factor = factor
            but.clicked.connect(self.on_gain_zoom)
            h.addWidget(but)
    
    @property
    def viewer(self):
        return self._viewer()

    @property
    def selected(self):
        selected = np.ones(self.viewer.nb_channel, dtype=bool)
        if self.viewer.nb_channel>1:
            selected[:] = False
            selected[[ind.row() for ind in self.qlist.selectedIndexes()]] = True
        return selected
    
    def on_set_visible(self):
        # apply
        visibles = self.selected
        for i,param in enumerate(self.viewer.by_channel_params.children()):
            param['visible'] = visibles[i]
    
    def on_auto_gain_and_offset(self):
        mode = self.sender().mode
        self.viewer.auto_gain_and_offset(mode=mode, visibles=self.selected)
    
    def on_gain_zoom(self):
        factor = self.sender().factor
        self.viewer.gain_zoom(factor, selected=self.selected)
