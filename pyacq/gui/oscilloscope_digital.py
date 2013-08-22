# -*- coding: utf-8 -*-

from PyQt4 import QtCore,QtGui
import pyqtgraph as pg
import zmq

from .tools import RecvPosThread
from .guiutil import *
from .multichannelparam import MultiChannelParam

from matplotlib.cm import get_cmap
from matplotlib.colors import ColorConverter


param_global = [
    {'name': 'xsize', 'type': 'logfloat', 'value': 1., 'step': 0.1},
    {'name': 'background_color', 'type': 'color', 'value': 'k' },
    {'name': 'refresh_interval', 'type': 'int', 'value': 100 , 'limits':[5, 1000]},
    {'name': 'mode', 'type': 'list', 'value': 'scan' , 'values' : ['scan', 'scroll'] },
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

class OscilloscopeDigital(QtGui.QWidget):
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
        for i, channel_name in zip(range(n),  stream['channel_names']):
            color = self.paramChannels.children()[i]['color']
            #~ curve = self.plot.plot([np.nan], [np.nan], pen = color)
            #~ self.curves.append(curve)
            curve = pg.PlotCurveItem(pen = color)
            self.plot.addItem(curve)
            self.curves.append(curve)
        
        self.paramGlobal.param('xsize').setValue(3)

    def open_configure_dialog(self):
        self.paramControler.show()    
    
    def change_param_channel(self, channel, **kargs):
        p  = self.paramChannels.children()[channel]
        for k, v in kargs.items():
            p.param(k).setValue(v)
        
    def change_param_global(self, **kargs):
        for k, v in kargs.items():
            self.paramGlobal.param(k).setValue(v)
    
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
            if param.name()=='background_color':
                self.graphicsview.setBackground(data)
            if param.name()=='xsize':
                xsize = data
                sr = self.stream['sampling_rate']
                self.intsize = int(xsize*sr)
                self.t_vect = np.arange(self.intsize, dtype = float)/sr
                self.t_vect -= self.t_vect[-1]
                self.curves_data = [ np.zeros( ( self.intsize), dtype =float) for i in range(self.stream['nb_channel']) ]
                
            if param.name()=='refresh_interval':
                self.timer.setInterval(data)
            if param.name()=='mode':
                self.curves_data = [ np.zeros( ( self.intsize), dtype =float) for i in range(self.stream['nb_channel']) ]
                self.last_pos = self.thread_pos.pos


    def refresh(self):
        if self.thread_pos.pos is None: return
        pos = self.thread_pos.pos

        mode = self.paramGlobal['mode']
        visibles = np.array([p['visible'] for p in self.paramChannels.children()], dtype = bool)
        n = np.sum(visibles)
        
        if mode=='scroll':
            head = pos%self.half_size+self.half_size
            tail = head-self.intsize
            np_arr = self.np_array[:, tail:head]
            o = n-1
            for c, v in zip(range(visibles.size),  visibles):
                if v :
                    self.curves_data[c] = extract_bit(c, np_arr)*.8+o
                    o -=1 
        else:
            new = (pos-self.last_pos)
            if new>=self.intsize: new = self.intsize-1
            head = pos%self.half_size+self.half_size
            tail = head - new
            np_arr = self.np_array[:, tail:head]
            i1 = (pos-new)%self.intsize
            i2 = pos%self.intsize
            if i1>i2:
                o = n-1
                for c in range(visibles.size):
                    if visibles[c]:
                        self.curves_data[c][i1:] = extract_bit(c,np_arr[:,:self.intsize-i1])*.8+o
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
    
    
            
    
    def automatic_color(self, cmap_name = None, selected = None):
        nb_channel = self.stream['nb_channel']
        if selected is None:
            selected = np.ones(nb_channel, dtype = bool)
        
        if cmap_name is None:
            cmap_name = 'jet'
        n = np.sum(selected)
        if n==0: return
        cmap = get_cmap(cmap_name , n)
        s=0
        for i in range(self.stream['nb_channel']):
            if selected[i]:
                color = [ int(c*255) for c in ColorConverter().to_rgb(cmap(s)) ]
                self.change_param_channel(i,  color = color)
                s += 1


            



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
            


