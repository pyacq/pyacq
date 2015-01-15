# -*- coding: utf-8 -*-

from PyQt4 import QtCore,QtGui
import pyqtgraph as pg
import zmq

from .tools import RecvPosThread, MultiChannelParamsSetter
from .guiutil import *
from .multichannelparam import MultiChannelParam

from matplotlib.cm import get_cmap
from matplotlib.colors import ColorConverter


param_global = [
    {'name': 'xsize', 'type': 'logfloat', 'value': 1., 'step': 0.1},
    {'name': 'background_color', 'type': 'color', 'value': 'k' },
    {'name': 'refresh_interval', 'type': 'int', 'value': 100 , 'limits':[5, 1000]},
    {'name': 'mode', 'type': 'list', 'value': 'scan' , 'values' : ['scan', 'scroll'] },
    {'name': 'auto_decimate', 'type': 'bool', 'value':  True },
    {'name': 'decimate', 'type': 'int', 'value': 1.,  'limits' : [1, None], },
    {'name': 'display_labels', 'type': 'bool', 'value': False },
    ]

param_by_channel = [ 
    {'name': 'color', 'type': 'color', 'value': '#7FFF00'},
    {'name': 'visible', 'type': 'bool', 'value': True},
    ]


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
        if ev.modifiers() ==  Qt.ControlModifier:
            z = 10 if ev.delta()>0 else 1/10.
        else:
            z = 1.3 if ev.delta()>0 else 1/1.3
        self.zoom.emit(z)
        ev.accept()


def extract_bit(chan, arr):
    b = chan//8
    mask = 1<<(chan%8)
    return (arr[b,:]&mask>0).astype(float)

class OscilloscopeDigital(QtGui.QWidget, MultiChannelParamsSetter):
    _param_global =param_global
    _param_by_channel = param_by_channel
    
    def __init__(self, stream = None, parent = None,):
        QtGui.QWidget.__init__(self, parent)
        
        assert type(stream).__name__ == 'DigitalSignalSharedMemStream'
        
        self.stream = stream
        

        self.mainlayout = QtGui.QVBoxLayout()
        self.setLayout(self.mainlayout)
        self.viewBox = MyViewBox()
        self.viewBox.doubleclicked.connect(self.open_configure_dialog)
        self.graphicsview  = pg.GraphicsView()#useOpenGL = True)
        self.mainlayout.addWidget(self.graphicsview)
        self.plot = pg.PlotItem(viewBox = self.viewBox)
        self.graphicsview.setCentralItem(self.plot)
        
        self.context = zmq.Context()
        self.socket = self.context.socket(zmq.SUB)
        self.socket.setsockopt(zmq.SUBSCRIBE,'')
        self.socket.connect("tcp://localhost:{}".format(self.stream['port']))
        
        self.thread_pos = RecvPosThread(socket = self.socket, port = self.stream['port'])
        self.thread_pos.start()
        
        self.last_pos = 0
        self.all_mean, self.all_sd = None, None
        
        self.timer = QtCore.QTimer(interval = 100)
        self.timer.timeout.connect(self.refresh)
        self.timer.start()
        
        # Create parameters
        n = stream['nb_channel']
        self.np_array = self.stream['shared_array'].to_numpy_array()
        self.half_size = self.np_array.shape[1]/2
        sr = self.stream['sampling_rate']
        
        all = [ ]
        for i, channel_name in zip(range(n),  stream['channel_names']):
            name = 'Signal{} name={} '.format(i,channel_name)
            all.append({ 'name': name, 'type' : 'group', 'children' : param_by_channel})
        self.paramChannels = pg.parametertree.Parameter.create(name='AnalogSignals', type='group', children=all)
        self.paramGlobal = pg.parametertree.Parameter.create( name='Global options',
                                                    type='group', children =param_global)
        self.allParams = pg.parametertree.Parameter.create(name = 'all param', type = 'group', children = [self.paramGlobal,self.paramChannels  ])
        
        self.allParams.sigTreeStateChanged.connect(self.on_param_change)
        self.paramGlobal.param('xsize').setLimits([2./sr, self.half_size/sr*.95])
        
        
        self.paramControler = OscilloscopeControler(parent = self)
        self.paramControler.setWindowFlags(Qt.Window)

        
        # Create curve items
        self.curves = [ ]
        self.channel_labels = [ ]
        for i, channel_name in zip(range(n),  stream['channel_names']):
            color = self.paramChannels.children()[i]['color']
            #~ curve = self.plot.plot([np.nan], [np.nan], pen = color)
            #~ self.curves.append(curve)
            curve = pg.PlotCurveItem(pen = color)
            self.plot.addItem(curve)
            self.curves.append(curve)
            label = pg.TextItem(self.stream['channel_names'][i], color = color,  anchor=(0.5, 0.5), border=None,  fill=pg.mkColor((128,128,128, 200)))
            self.plot.addItem(label)
            self.channel_labels.append(label)
        
        self.paramGlobal.param('xsize').setValue(3)

    def stop(self):
        self.timer.stop()
        self.thread_pos.stop()
        self.thread_pos.wait()

    def open_configure_dialog(self):
        self.paramControler.show()    

    
    def on_param_change(self, params, changes):
        for param, change, data in changes:
            if change != 'value': continue
            if param.name()=='ylims':
                continue
            if param.name()=='visible':
                c = self.paramChannels.children().index(param.parent())
                if data:
                    self.curves[c].show()
                else:
                    self.curves[c].hide()
            if param.name()=='color':
                i = self.paramChannels.children().index(param.parent())
                pen = pg.mkPen(color = data)
                self.curves[i].setPen(pen)
                self.channel_labels[i].setText(self.stream['channel_names'][i], color = data)
            if param.name()=='background_color':
                self.graphicsview.setBackground(data)
            if param.name()=='xsize':
                if self.paramGlobal['auto_decimate']:
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
                self.last_pos = self.thread_pos.pos
    
    def estimate_decimate(self):
        xsize = self.paramGlobal['xsize']
        sr = self.stream['sampling_rate']
        self.paramGlobal['decimate'] = max( int(xsize*sr)//4000, 1)
    
    def reset_curves_data(self):
        xsize = self.paramGlobal['xsize']
        decimate = self.paramGlobal['decimate']
        sr = self.stream['sampling_rate']
        self.intsize = int(xsize*sr)
        self.t_vect = np.arange(0,self.intsize//decimate, dtype = float)/(sr/decimate)
        self.t_vect -= self.t_vect[-1]
        self.curves_data = [ np.zeros( ( self.intsize//decimate), dtype =float) for i in range(self.stream['nb_channel']) ]

    

    def refresh(self):
        if self.thread_pos.pos is None: return
        
        decimate = self.paramGlobal['decimate']
        mode = self.paramGlobal['mode']
        visibles = np.array([p['visible'] for p in self.paramChannels.children()], dtype = bool)
        n = np.sum(visibles)
        
        
        pos = self.thread_pos.pos
        if decimate>1:
            pos = pos - pos%decimate

        if self.last_pos>pos:
            # the stream have restart from zeros
            self.last_pos = 0
            for curve_data in self.curves_data:
                curve_data[:] = 0.
        
        if mode=='scroll':
            head = pos%self.half_size+self.half_size
            head = head - head%decimate
            tail = head-(self.intsize-self.intsize%decimate)
            np_arr = self.np_array[:, tail:head:decimate]
            o = n-1
            for c, v in zip(range(visibles.size),  visibles):
                if v :
                    self.curves_data[c] = extract_bit(c, np_arr)*.8+o
                    o -=1 
        else:
            new = (pos-self.last_pos)
            if new>=self.intsize: new = self.intsize-1
            head = pos%self.half_size+self.half_size
            head = head - head%decimate
            new = new-new%decimate
            tail = head - new
            np_arr = self.np_array[:, tail:head:decimate]
            
            i1 = (pos-new)%self.intsize
            i2 = pos%self.intsize
            if decimate>1:
                i1 = i1//decimate
                i2 = i2//decimate
            if i1>i2:
                o = n-1
                for c in range(visibles.size):
                    if visibles[c]:
                        self.curves_data[c][i1:] = extract_bit(c,np_arr[:,:self.intsize//decimate-i1])*.8+o
                        if i2!=0:
                            self.curves_data[c][:i2] = extract_bit(c, np_arr[:,-i2:])*.8+o
                        o -= 1 
            else:
                o = n-1
                for c in range(visibles.size):
                    if visibles[c]:
                        self.curves_data[c][i1:i2] = extract_bit(c,np_arr)*.8+o
                        o -= 1 
            self.last_pos = pos
        
        for c, curve in enumerate(self.curves):
            if visibles[c]: 
                curve.setData(self.t_vect, self.curves_data[c], antialias = False)
        
        self.plot.setXRange( self.t_vect[0], self.t_vect[-1])
        self.plot.setYRange( -.5,n+.5  )
        
        o = n-1
        for c in range(visibles.size):
            label = self.channel_labels[c]
            if visibles[c] and self.paramGlobal['display_labels']:
                label.setPos(-self.paramGlobal['xsize'],  o)
                label.setVisible(True)
                o -= 1 
            else:
                label.setVisible(False)
    
            
    
    def automatic_color(self, cmap_name = None, selected = None):
        nb_channel = self.stream['nb_channel']
        if selected is None:
            selected = np.ones(nb_channel, dtype = bool)
        
        if cmap_name is None:
            cmap_name = 'jet'
        n = np.sum(selected)
        if n==0: return
        cmap = get_cmap(cmap_name , n)
        colors = self.get_params()['colors']
        s=0
        for i in range(self.stream['nb_channel']):
            if selected[i]:
                colors[i] = [ int(c*255) for c in ColorConverter().to_rgb(cmap(s)) ]
                s += 1
        self.set_params(colors = colors)


            



class OscilloscopeControler(QtGui.QWidget):
    def __init__(self, parent = None):
        QtGui.QWidget.__init__(self, parent)
        
        self.viewer = parent

        #layout
        self.mainlayout = QtGui.QVBoxLayout()
        self.setLayout(self.mainlayout)
        t = u'Options for signals - {}'.format(self.viewer.stream['name'])
        self.setWindowTitle(t)
        self.mainlayout.addWidget(QLabel('<b>'+t+'<\b>'))
        
        h = QtGui.QHBoxLayout()
        self.mainlayout.addLayout(h)
        
        self.treeParamSignal = pg.parametertree.ParameterTree()
        self.treeParamSignal.header().hide()
        h.addWidget(self.treeParamSignal)
        self.treeParamSignal.setParameters(self.viewer.paramChannels, showTop=True)
        
        if self.viewer.stream['nb_channel']>1:
            self.multi = MultiChannelParam( all_params = self.viewer.paramChannels, param_by_channel = param_by_channel)
            h.addWidget(self.multi)
        
        v = QtGui.QVBoxLayout()
        h.addLayout(v)
        
        self.treeParamGlobal = pg.parametertree.ParameterTree()
        self.treeParamGlobal.header().hide()
        v.addWidget(self.treeParamGlobal)
        self.treeParamGlobal.setParameters(self.viewer.paramGlobal, showTop=True)

        # 
        v.addWidget(QLabel(self.tr('<b>Automatic color on selection:<\b>'),self))
        but = QPushButton('Progressive')
        but.clicked.connect(self.on_automatic_color)
        v.addWidget(but)

    
    def on_automatic_color(self, cmap_name = None):
        cmap_name = 'jet'
        if self.viewer.stream['nb_channel']>1:
            selected = self.multi.selected()
        else:
            selected = np.ones(1, dtype = bool)
        self.viewer.automatic_color(cmap_name = cmap_name, selected = selected)
            


