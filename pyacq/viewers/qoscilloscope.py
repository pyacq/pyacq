from ..core import WidgetNode, register_node_type, StreamConverter, InputStream
from pyqtgraph.Qt import QtCore, QtGui

import numpy as np
import pyqtgraph as pg


class MyViewBox(pg.ViewBox):
    doubleclicked = QtCore.pyqtSignal()
    zoom = QtCore.pyqtSignal(float)
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
        if ev.modifiers() ==  QtCore.Qt.ControlModifier:
            z = 10 if ev.delta()>0 else 1/10.
        else:
            z = 1.3 if ev.delta()>0 else 1/1.3
        self.zoom.emit(z)
        ev.accept()


class BaseOscilloscope(WidgetNode):
    """
    Base Class for QOscilloscope and QOscilloscopeDigital
    
    The BaseOscilloscope need a transfermode = sharedarray.
    
    If the inputstream is not a sharedarray its create it own prox input with a node converter.
    
    """
    def __init__(self, **kargs):
        WidgetNode.__init__(self, **kargs)
        
        self.layout = QtGui.QHBoxLayout()
        self.setLayout(self.layout)
        
        self.graphicsview  = pg.GraphicsView()
        self.layout.addWidget(self.graphicsview)
        
        # create graphic view and plot item
        self.viewBox = MyViewBox()
        #~ self.viewBox.doubleclicked.connect(self.open_configure_dialog)
        self.plot = pg.PlotItem(viewBox = self.viewBox)
        self.graphicsview.setCentralItem(self.plot)
        self.plot.hideButtons()
        self.plot.showAxis('left', False)
        self.plot.showAxis('bottom', False)
        
        self.all_mean, self.all_sd = None, None
        
        
        #~ self.paramControler = OscilloscopeControler(parent = self)
        #~ self.paramControler.setWindowFlags(Qt.Window)
        
    #~ def open_configure_dialog(self):
        #~ self.paramControler.show()
        
    
    
    def _configure(self, **kargs):
        pass
    
    def _initialize(self):
        assert len(self.input.params['shape']) == 2, 'Are you joking ?'
        d0, d1 = self.input.params['shape']
        if self.input.params['timeaxis']==0:
            self.nb_channel  = d1
        else:
            self.nb_channel  = d0
        
        sr = self.input.params['sampling_rate']
        #create proxy input
        if self.input.params['transfermode'] == 'sharedarray' and self.input.params['timeaxis'] == 1:
            self.proxy_input = self.input
            self.conv = None
        else:
            # if input is not transfermode creat a proxy
            self.conv = StreamConverter()
            self.conv.configure()
            print(self.input.params)
            self.conv.input.connect(self.input.params)
            print(self.conv.input.params)
            if self.input.params['timeaxis']==0:
                new_shape = (d1, d0)
            else:
                new_shape = (d0, d1)
            self.conv.output.configure(protocol = 'inproc', interface = '127.0.0.1', port='*', 
                   transfermode = 'sharedarray', streamtype = 'analogsignal',
                   dtype = 'float32', shape = new_shape, timeaxis = 1, 
                   compression ='', scale = None, offset = None, units = '',
                   sharedarray_shape = (self.nb_channel, int(sr*60.)), ring_buffer_method = 'double',
                   )
            self.conv.initialize()
            self.proxy_input = InputStream()
            self.proxy_input.connect(self.conv.output)
            

        # Create parameters

        all = [ ]
        for i in range(self.nb_channel):
            name = 'Signal{}'.format(i)
            all.append({ 'name': name, 'type' : 'group', 'children' : self._param_by_channel})
        self.paramChannels = pg.parametertree.Parameter.create(name='AnalogSignals', type='group', children=all)
        self.paramGlobal = pg.parametertree.Parameter.create( name='Global options',
                                                    type='group', children =self._param_global)
        self.allParams = pg.parametertree.Parameter.create(name = 'all param', type = 'group', children = [self.paramGlobal,self.paramChannels  ])
        #~ self.allParams.sigTreeStateChanged.connect(self.on_param_change)
        
        #timer
        self._head = 0
        self.timer = QtCore.QTimer(singleShot=False, interval = 100)
        self.timer.timeout.connect(self.refresh)

    def _start(self):
        if self.conv is not None:
            self.conv.start()
        self.timer.start()

    def _stop(self):
        if self.conv is not None:
            self.conv.stop()        
        self.timer.stop()
    
    def _close(self):
        pass

    def refresh(self):
        #check for new head in socket
        while self.proxy_input.socket.poll(0):
            self._head, _ = self.proxy_input.recv()
        self._refresh()



param_global = [
    {'name': 'xsize', 'type': 'float', 'value': 3., 'step': 0.1},
    #~ {'name': 'ylims', 'type': 'range', 'value': [-10., 10.] },
    {'name': 'background_color', 'type': 'color', 'value': 'k' },
    {'name': 'refresh_interval', 'type': 'int', 'value': 100 , 'limits':[5, 1000]},
    {'name': 'mode', 'type': 'list', 'value': 'scan' , 'values' : ['scan', 'scroll'] },
    {'name': 'auto_decimate', 'type': 'bool', 'value':  True },
    {'name': 'decimate', 'type': 'int', 'value': 1., 'limits' : [1, None], },
    {'name': 'display_labels', 'type': 'bool', 'value': False },
    ]

param_by_channel = [ 
    {'name': 'color', 'type': 'color', 'value': '#7FFF00'},
    {'name': 'gain', 'type': 'float', 'value': 1, 'step': 0.1},
    {'name': 'offset', 'type': 'float', 'value': 0., 'step': 0.1},
    {'name': 'visible', 'type': 'bool', 'value': True},
    ]

class QOscilloscope(BaseOscilloscope):
    """
    Continuous oscilloscope for multi signals.
    Based on Qt and pyqtgraph.
    Should be rewritten in vispy for optimisation.    
    """
    _input_specs = {'video' : dict(streamtype = 'video',dtype = 'uint8',
                                                shape = (-1, -1, 3), compression ='',
                                                ),
                                }
    _param_global =param_global
    _param_by_channel = param_by_channel
    
    def __init__(self, **kargs):
        BaseOscilloscope.__init__(self, **kargs)
        
        self.viewBox.zoom.connect(self.gain_zoom)
        
    def _initialize(self):
        BaseOscilloscope._initialize(self)
        
        self.curves = [ ]
        self.channel_labels = [ ]
        for i in range(self.nb_channel):
            color = self.paramChannels.children()[i]['color']
            curve = pg.PlotCurveItem(pen = color)
            self.plot.addItem(curve)
            self.curves.append(curve)
            label = pg.TextItem('TODO name{}'.format(i), color = color,  anchor=(0.5, 0.5), border=None,  fill=pg.mkColor((128,128,128, 200)))
            self.plot.addItem(label)
            self.channel_labels.append(label)
        sr = self.input.params['sampling_rate']
        #~ self.paramGlobal.param('xsize').setLimits([2./sr, self.half_size/sr*.95])
        #~ self.paramGlobal['xsize'] = 3.# to reset curves
        
        self.reset_curves_data()
    
    def _refresh(self):
        mode = self.paramGlobal['mode']
        decimate = int(self.paramGlobal['decimate'])
        gains = np.array([p['gain'] for p in self.paramChannels.children()])
        offsets = np.array([p['offset'] for p in self.paramChannels.children()])
        visibles = np.array([p['visible'] for p in self.paramChannels.children()], dtype = bool)
        sr = self.input.params['sampling_rate']
        xsize = self.paramGlobal['xsize'] 
        intsize = int(xsize*sr)#TODOs
        
        #TODO:
        #   * pos>head
      
        head = self._head
        if decimate>1:
            head = head - head%decimate
        
        
        
        np_arr = self.proxy_input.get_array_slice(head,intsize)
        
        #TODO several decimation medthos
        np_arr = np_arr[:,::decimate]
        
        
        #gain/offset
        #~ np_arr[visibles, :] = np_arr[visibles, :]*gains[visibles, None]+offsets[visibles, None]
        
        if mode=='scroll':
            for c, visible in enumerate(visibles):
                if visible:
                    self.curves_data[c] = np_arr[c,:]
        elif mode =='scan':
            ind = (head//decimate)%np_arr.shape[1]
            for c, visible in enumerate(visibles):
                if visible:
                    self.curves_data[c] = np.concatenate((np_arr[c,-ind:], np_arr[c,:-ind]))

        for c, visible in enumerate(visibles):
            if visible:
               self.curves[c].setData(self.t_vect, self.curves_data[c], antialias = False)
            
        self.plot.setXRange( self.t_vect[0], self.t_vect[-1])
        #~ ylims  = self.paramGlobal['ylims']
        self.plot.setYRange( -1., 1. )

        for c, visible in enumerate(visibles):
            label = self.channel_labels[c]
            if visible and self.paramGlobal['display_labels']:
                if self.all_mean is not None:
                    label.setPos(-self.paramGlobal['xsize'],  self.all_mean[c]*gains[c]+offsets[c])
                else:
                    label.setPos(-self.paramGlobal['xsize'],  offsets[c])
                label.setVisible(True)
            else:
                label.setVisible(False)

    def gain_zoom(self, factor):
        for i, p in enumerate(self.paramChannels.children()):
            if self.all_mean is not None:
                p['offset'] = p['offset'] + self.all_mean[i]*p['gain'] - self.all_mean[i]*p['gain']*factor
            p['gain'] = p['gain']*factor

    #~ def autoestimate_scales(self):
        #~ if self.head is None:
            #~ return None, None
        #~ head = self.head
        #~ intsize = self.intsize
        #~ np_arr = self.proxy_input.get_array_slice(head,intsize)
        #~ self.all_sd = np.std(np_arr, axis = 1)
        #~ #self.all_mean = np.mean(np_arr, axis = 1)
        #~ self.all_mean = np.median(np_arr, axis = 1)
        #~ return self.all_mean, self.all_sd
    
    def reset_curves_data(self):
        xsize = self.paramGlobal['xsize']
        decimate = self.paramGlobal['decimate']
        sr = self.input.params['sampling_rate']
        self.intsize = int(xsize*sr)
        self.t_vect = np.arange(0,self.intsize//decimate, dtype = float)/(sr/decimate)
        self.t_vect -= self.t_vect[-1]
        self.curves_data = [ np.zeros( ( self.intsize//decimate), dtype =float) for i in range(self.nb_channel) ]
        

    

register_node_type(QOscilloscope)
