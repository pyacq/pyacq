# -*- coding: utf-8 -*-

from PyQt4 import QtCore,QtGui
import pyqtgraph as pg
import zmq

from .tools import RecvPosThread, MultiChannelParamsSetter
from .guiutil import *
from .multichannelparam import MultiChannelParam

import time

from matplotlib.cm import get_cmap
from matplotlib.colors import ColorConverter
#~ import copy

param_global = [
    {'name': 'xsize', 'type': 'logfloat', 'value': 1., 'step': 0.1},
    {'name': 'ylims', 'type': 'range', 'value': [-10., 10.] },
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


class BaseOscilloscope(QtGui.QWidget, MultiChannelParamsSetter):
    def __init__(self, stream = None, parent = None,):
        QtGui.QWidget.__init__(self, parent)
        
        assert type(stream).__name__ == 'AnalogSignalSharedMemStream'
        
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
        
        self.all_mean, self.all_sd = None, None
        
        self.timer = QtCore.QTimer(interval = 100)
        self.timer.timeout.connect(self.refresh)
        

        # Create parameters
        n = stream['nb_channel']
        self.np_array = self.stream['shared_array'].to_numpy_array()
        self.half_size = self.np_array.shape[1]/2
        sr = self.stream['sampling_rate']

        all = [ ]
        for i, channel_index, channel_name in zip(range(n), stream['channel_indexes'], stream['channel_names']):
            name = 'Signal{} name={} channel_index={}'.format(i, channel_name,channel_index)
            all.append({ 'name': name, 'type' : 'group', 'children' : self._param_by_channel})
        self.paramChannels = pg.parametertree.Parameter.create(name='AnalogSignals', type='group', children=all)
        self.paramGlobal = pg.parametertree.Parameter.create( name='Global options',
                                                    type='group', children =self._param_global)
        self.allParams = pg.parametertree.Parameter.create(name = 'all param', type = 'group', children = [self.paramGlobal,self.paramChannels  ])
        self.allParams.sigTreeStateChanged.connect(self.on_param_change)
        
        self.paramControler = OscilloscopeControler(parent = self)
        self.paramControler.setWindowFlags(Qt.Window)
        self.viewBox.zoom.connect(self.gain_zoom)
        

    def open_configure_dialog(self):
        self.paramControler.show()
    
    def start(self):
        self.timer.start()
    
    def stop(self):
        self.timer.stop()



    def auto_gain_and_offset(self, mode = 0, selected = None):
        """
        mode = 0, 1, 2
        """
        nb_channel = self.stream['nb_channel']
        if selected is None:
            selected = np.ones(nb_channel, dtype = bool)
        
        n = np.sum(selected)
        if n==0: return
        
        av, sd = self.autoestimate_scales()
        if av is None: return
        
        if mode==0:
            ylims = [np.min(av[selected]-3*sd[selected]), np.max(av[selected]+3*sd[selected]) ]
            gains = np.ones(nb_channel, dtype = float)
            offsets = np.zeros(nb_channel, dtype = float)
        elif mode in [1, 2]:
            ylims  = [-.5, n-.5 ]
            gains = np.ones(nb_channel, dtype = float)
            if mode==1 and max(sd[selected])!=0:
                gains = np.ones(nb_channel, dtype = float) * 1./(6.*max(sd[selected]))
            elif mode==2 :
                gains[sd!=0] = 1./(6.*sd[sd!=0])
            offsets = np.zeros(nb_channel, dtype = float)
            offsets[selected] = range(n)[::-1] - av[selected]*gains[selected]
        
        # apply
        self.set_params(gains = gains.tolist(), offsets = offsets.tolist(), visibles = selected.tolist(),
                                        ylims = ylims)

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
        
    def gain_zoom(self, factor):
        for i, p in enumerate(self.paramChannels.children()):
            if self.all_mean is not None:
                p['offset'] = p['offset'] + self.all_mean[i]*p['gain'] - self.all_mean[i]*p['gain']*factor
            p['gain'] = p['gain']*factor




class Oscilloscope(BaseOscilloscope):
    _param_global =param_global
    _param_by_channel = param_by_channel
    
    def __init__(self, stream = None, parent = None,):
        
        
        
        BaseOscilloscope.__init__(self, stream = stream, parent = parent,)

        # Create curve items
        
        self.curves = [ ]
        self.channel_labels = [ ]
        for i in range(self.stream['nb_channel']):
            color = self.paramChannels.children()[i]['color']
            curve = pg.PlotCurveItem(pen = color)
            self.plot.addItem(curve)
            self.curves.append(curve)
            label = pg.TextItem(self.stream['channel_names'][i], color = color,  anchor=(0.5, 0.5), border=None,  fill=pg.mkColor((128,128,128, 200)))
            self.plot.addItem(label)
            self.channel_labels.append(label)
        sr = self.stream['sampling_rate']
        self.paramGlobal.param('xsize').setLimits([2./sr, self.half_size/sr*.95])
        self.paramGlobal['xsize'] = 3.# to reset curves
        
        self.start()
    
    def start(self):
        self.thread_pos = RecvPosThread(socket = self.socket, port = self.stream['port'])
        self.thread_pos.start()
        self.last_pos = 0
        BaseOscilloscope.start(self)

    def stop(self):
        BaseOscilloscope.stop(self)
        self.thread_pos.stop()
        self.thread_pos.wait()
    
    
    def on_param_change(self, params, changes):
        #~ print 'on_param_change'
        for param, change, data in changes:
            if change != 'value': continue
            #~ print param.name()
            if param.name() in ['gain', 'offset']: 
                #~ print 'ici', self.thread_pos.pos, self.intsize
                if self.thread_pos.pos is not None:
                    self.last_pos = self.thread_pos.pos - self.intsize
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

        mode = self.paramGlobal['mode']
        decimate = self.paramGlobal['decimate']
        gains = np.array([p['gain'] for p in self.paramChannels.children()])
        offsets = np.array([p['offset'] for p in self.paramChannels.children()])
        visibles = np.array([p['visible'] for p in self.paramChannels.children()], dtype = bool)

        pos = self.thread_pos.pos
        if decimate>1:
            pos = pos - pos%decimate
        last_pos = self.last_pos #can be modifyed during refresh!!
        
        if last_pos>pos:
            # the stream have restart from zeros
            last_pos = self.last_pos = 0
            for curve_data in self.curves_data:
                curve_data[:] = 0.
        
        
        if mode=='scroll':
            head = pos%self.half_size+self.half_size
            head = head - head%decimate
            tail = head-(self.intsize-self.intsize%decimate)
            np_arr = self.np_array[:, tail:head:decimate]
            
            #~ head = pos%self.half_size+self.half_size
            #~ tail = head-self.intsize
            #~ np_arr = self.np_array[:, tail:head]
            for c, g, o,v in zip(range(gains.size), gains, offsets, visibles):
                if v :
                    self.curves_data[c] = np_arr[c,:]*g+o
        else:
            new = (pos-last_pos)
            if new>=(self.intsize-decimate-1): new = self.intsize-decimate-1
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
            #~ new = (pos-self.last_pos)
            #~ if new>=self.intsize: new = self.intsize-1
            #~ head = pos%self.half_size+self.half_size
            #~ tail = head - new
            #~ np_arr = self.np_array[:, tail:head]
            #~ i1 = (pos-new)%self.intsize
            #~ i2 = pos%self.intsize
            if i1>i2:
                for c in range(gains.size):
                    if visibles[c]:
                        #~ self.curves_data[c][i1:] = np_arr[c,:self.intsize-i1]*gains[c]+offsets[c]
                        self.curves_data[c][i1:] = np_arr[c,:self.intsize//decimate-i1]*gains[c]+offsets[c]
                        if i2!=0:
                            self.curves_data[c][:i2] = np_arr[c,-i2:]*gains[c]+offsets[c]
            #~ else:
            elif i1<i2:
                for c in range(gains.size):
                    if visibles[c]:
                        #~ try:
                        self.curves_data[c][i1:i2] = np_arr[c,:]*gains[c]+offsets[c]
                        #~ except:
                            #~ print i1, i2, decimate, np_arr.shape, (pos-new)%self.intsize, pos%self.intsize, new, head, tail
            else:
                if np_arr.shape[1]!=0:
                    print 'bug arrondi!!!'
                    print i1, i2, decimate, np_arr.shape, (pos-new)%self.intsize, pos%self.intsize, new, head, tail, head-tail, self.intsize, self.intsize//decimate
        self.last_pos = pos
        
        for c, curve in enumerate(self.curves):
            p = self.paramChannels.children()[c]
            if not p['visible']:  continue
            curve.setData(self.t_vect, self.curves_data[c], antialias = False)
            # Does this optmize ???
            #~ curve.path = None
            #~ curve.fillPath = None            
            #~ curve.update()            
            
            
        self.plot.setXRange( self.t_vect[0], self.t_vect[-1])
        ylims  =self.paramGlobal['ylims']
        self.plot.setYRange( *ylims )
        
        for c in range(gains.size):
            label = self.channel_labels[c]
            if visibles[c] and self.paramGlobal['display_labels']:
                if self.all_mean is not None:
                    label.setPos(-self.paramGlobal['xsize'],  self.all_mean[c]*gains[c]+offsets[c])
                else:
                    label.setPos(-self.paramGlobal['xsize'],  offsets[c])
                label.setVisible(True)
            else:
                label.setVisible(False)
    
    #
    def autoestimate_scales(self):
        if self.thread_pos.pos is None: 
            self.all_mean, self.all_sd = None, None
            return None, None
        pos =self.thread_pos.pos
        head = pos%self.half_size+self.half_size
        tail = head-self.intsize
        n = self.stream['nb_channel']
        #~ self.all_mean =  np.array([ np.mean(self.np_array[i,tail:head]) for i in range(n) ])
        self.all_sd = np.array([ np.std(self.np_array[i,tail:head]) for i in range(n) ])
        # better than std and mean
        self.all_mean = np.array([ np.median(self.np_array[i,tail:head]) for i in range(n) ])
        #~ self.all_sd=  np.array([ np.median(np.abs(self.np_array[i,:tail:head]-self.all_mean[i])/.6745) for i in range(n) ])
        #~ print self.all_mean, self.all_sd
        return self.all_mean, self.all_sd

    


        

            
            



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

        # Gain and offset
        v.addWidget(QLabel(u'<b>Automatic gain and offset on selection:<\b>'))
        for i,text in enumerate(['Real scale (gain = 1, offset = 0)',
                            'Fake scale (same gain for all)',
                            'Fake scale (gain per channel)',]):
            but = QPushButton(text)
            v.addWidget(but)
            but.mode = i
            but.clicked.connect(self.on_auto_gain_and_offset)

        v.addWidget(QLabel(self.tr('<b>Automatic color on selection:<\b>'),self))
        h = QtGui.QHBoxLayout()
        but = QPushButton('Progressive')
        but.clicked.connect(self.on_automatic_color)
        h.addWidget(but,4)
        self.combo_cmap = QtGui.QComboBox()
        self.combo_cmap.addItems(['jet', 'prism', 'spring', 'spectral', 'hsv', 'autumn', 'spring', 'summer', 'winter', 'bone'])
        h.addWidget(self.combo_cmap,1)
        v.addLayout(h)

        v.addWidget(QLabel(self.tr('<b>Gain zoom (mouse wheel on graph):<\b>'),self))
        h = QHBoxLayout()
        v.addLayout(h)
        for label, factor in [ ('--', 1./10.), ('-', 1./1.3), ('+', 1.3), ('++', 10.),]:
            but = QPushButton(label)
            but.factor = factor
            but.clicked.connect(self.on_gain_zoom)
            h.addWidget(but)
    
    def on_auto_gain_and_offset(self):
        mode = self.sender().mode
        if self.viewer.stream['nb_channel']>1:
            selected = self.multi.selected()
        else:
            selected = np.ones(1, dtype = bool)
        self.viewer.auto_gain_and_offset(mode = mode, selected = selected)
    
    def on_automatic_color(self, cmap_name = None):
        #~ cmap_name = 'jet'
        cmap_name = str(self.combo_cmap.currentText())
        if self.viewer.stream['nb_channel']>1:
            selected = self.multi.selected()
        else:
            selected = np.ones(1, dtype = bool)
        self.viewer.automatic_color(cmap_name = cmap_name, selected = selected)
            
    def on_gain_zoom(self):
        factor = self.sender().factor
        self.viewer.gain_zoom(factor)

