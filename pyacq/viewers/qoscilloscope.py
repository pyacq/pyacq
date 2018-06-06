# -*- coding: utf-8 -*-
# Copyright (c) 2016, French National Center for Scientific Research (CNRS)
# Distributed under the (new) BSD License. See LICENSE for more info.

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
    def wheelEvent(self, ev, axis=None):
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
    
    If the input stream does not meet these requirements, then a StreamConverter
    is created to proxy the input. This can degrade performance when multiple
    Oscilloscopes are used to view data from the same device; in this case it is
    better to manually create single StreamConverter to provide shared input
    for all Oscilloscopes.
    """
    
    #In the code  willingly : self.input is self.inputs['signal'] because some subclass can have several inputs
    
    def __init__(self, **kargs):
        WidgetNode.__init__(self, **kargs)
        
        self.layout = QtGui.QVBoxLayout()
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
        
    def show_params_controller(self):
        self.params_controller.show()
        # TODO deal with modality
    
    def _configure(self, with_user_dialog=True, max_xsize=60.):
        self.with_user_dialog = with_user_dialog
        self.max_xsize = max_xsize
    
    def _initialize(self):
        assert len(self.inputs['signals'].params['shape']) == 2, 'Are you joking ?'
        self.nb_channel = self.inputs['signals'].params['shape'][1]
        self.sample_rate = self.inputs['signals'].params['sample_rate']
        buf_size = int(self.sample_rate * self.max_xsize)
        self.inputs['signals'].set_buffer(size=buf_size, axisorder=[1,0], double=True)
        #TODO : check that this not lead 
        
        # channel names
        channel_info = self.inputs['signals'].params.get('channel_info', None)
        if channel_info is None:
            self.channel_names = ['ch{}'.format(c) for c in range(self.nb_channel)]
        else:
            self.channel_names = [ch_info['name'] for ch_info in channel_info]

        # Create parameters
        all = []
        for i in range(self.nb_channel):
            pname = 'ch{}'.format(i)
            all.append({'name': pname, 'type': 'group', 'children': self._default_by_channel_params})
        self.by_channel_params = pg.parametertree.Parameter.create(name='AnalogSignals', type='group', children=all)
        self.params = pg.parametertree.Parameter.create(name='Global options',
                                                    type='group', children=self._default_params)
        self.all_params = pg.parametertree.Parameter.create(name='all param',
                                    type='group', children=[self.params, self.by_channel_params])
        self.all_params.sigTreeStateChanged.connect(self.on_param_change)
        
        
        if self.with_user_dialog and self._ControllerClass:
            self.params_controller = self._ControllerClass(parent=self, viewer=self)
            self.params_controller.setWindowFlags(QtCore.Qt.Window)
            self.viewBox.doubleclicked.connect(self.show_params_controller)
        else:
            self.params_controller = None
        
        # poller
        self.poller = ThreadPollInput(input_stream=self.inputs['signals'], return_data=None)
        self.poller.new_data.connect(self._on_new_data)
        # timer
        self._head = 0
        self.timer = QtCore.QTimer(singleShot=False, interval=100)
        self.timer.timeout.connect(self.refresh)

    def _start(self):
        self.estimate_decimate()
        self.reset_curves_data()
        self.poller.start()
        self.timer.start()
    
    def _stop(self):
        self.poller.stop()
        self.poller.wait()
        self.timer.stop()
    
    def _close(self):
        if self.running():
            self.stop()
        if self.with_user_dialog:
            self.params_controller.close()

    def _on_new_data(self, pos, data):
        self._head = pos
    
    def refresh(self):
        self._refresh()

    def reset_curves_data(self):
        xsize = self.params['xsize']
        decimate = self.params['decimate']
        #~ sr = self.input.params['sample_rate']
        self.full_size = int(xsize*self.sample_rate)
        self.small_size = self.full_size//decimate
        if self.small_size%2!=0:  # ensure for min_max decimate
            self.small_size -=1
        self.full_size = self.small_size*decimate
        self.t_vect = np.arange(0,self.small_size, dtype=float)/(self.sample_rate/decimate)
        self.t_vect -= self.t_vect[-1]
        self.curves_data = [np.zeros((self.small_size), dtype=float) for i in range(self.nb_channel)]

    def estimate_decimate(self, nb_point=4000):
        xsize = self.params['xsize']
        self.params['decimate'] = max(int(xsize*self.sample_rate)//nb_point, 1)

    def apply_xsize_zoom(self, xmove):
        factor = xmove/100.
        newsize = self.params['xsize']*(factor+1.)
        limits = self.params.param('xsize').opts['limits']
        if newsize>limits[0] and newsize<limits[1]:
            self.params['xsize'] = newsize


class OscilloscopeController(QtGui.QWidget):
    channel_visibility_changed = QtCore.pyqtSignal()
    
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
        
        self.v1 = QtGui.QVBoxLayout()
        h.addLayout(self.v1)
        self.tree_params = pg.parametertree.ParameterTree()
        self.tree_params.setParameters(self.viewer.params, showTop=True)
        self.tree_params.header().hide()
        self.v1.addWidget(self.tree_params)

        self.tree_by_channel_params = pg.parametertree.ParameterTree()
        self.tree_by_channel_params.header().hide()
        h.addWidget(self.tree_by_channel_params)
        self.tree_by_channel_params.setParameters(self.viewer.by_channel_params, showTop=True)

        v = QtGui.QVBoxLayout()
        h.addLayout(v)
        
        self.channel_visibility_changed.connect(self.on_channel_visibility_changed)

        but = QtGui.QPushButton('Auto scale')
        v.addWidget(but)
        #~ but.clicked.connect(self.compute_rescale)
        but.clicked.connect(self.on_channel_visibility_changed)
        
        
        if self.viewer.nb_channel>1:
            v.addWidget(QtGui.QLabel('<b>Select channel...</b>'))
            names = [ '{}: {}'.format(c, name) for c, name in enumerate(self.viewer.channel_names)]
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
    
    @property
    def visible_channels(self):
        visible = [self.viewer.by_channel_params['ch{}'.format(i), 'visible'] for i in range(self.viewer.nb_channel)]
        return np.array(visible, dtype='bool')

    @property
    def gains(self):
        gains = [self.viewer.by_channel_params['ch{}'.format(i), 'gain'] for i in range(self.viewer.nb_channel)]
        return np.array(gains)

    @gains.setter
    def gains(self, val):
        for c, v in enumerate(val):
            self.viewer.by_channel_params['ch{}'.format(c), 'gain'] = v

    @property
    def offsets(self):
        offsets = [self.viewer.by_channel_params['ch{}'.format(i), 'offset'] for i in range(self.viewer.nb_channel)]
        return np.array(offsets)

    @offsets.setter
    def offsets(self, val):
        for c, v in enumerate(val):
            self.viewer.by_channel_params['ch{}'.format(c), 'offset'] = v
    
    def on_set_visible(self):
        # apply
        self.viewer.by_channel_params.blockSignals(True)
        visibles = self.selected
        for i,param in enumerate(self.viewer.by_channel_params.children()):
            param['visible'] = visibles[i]
            if visibles[i]:
                self.viewer.curves[i].show()
            else:
                self.viewer.curves[i].hide()
        self.viewer.by_channel_params.blockSignals(False)
        self.channel_visibility_changed.emit()

    def on_channel_visibility_changed(self):
        self.compute_rescale()
        self.viewer.refresh()

    def estimate_median_mad(self):
        sigs = self.viewer.get_visible_chunk()
        self.signals_med = med = np.nanmedian(sigs, axis=0)
        self.signals_mad = np.nanmedian(np.abs(sigs-med),axis=0)*1.4826
        self.signals_min = np.min(sigs, axis=0)
        self.signals_max = np.max(sigs, axis=0)
    
    def compute_rescale(self, spacing_factor=9.):
        scale_mode = self.viewer.params['scale_mode']
        
        self.viewer.by_channel_params.blockSignals(True)
        
        gains = np.ones(self.viewer.nb_channel)
        offsets = np.zeros(self.viewer.nb_channel)
        nb_visible = np.sum(self.visible_channels)
        self.estimate_median_mad()
        
        if scale_mode=='real_scale':
            self.viewer.params['ylim_min'] = np.nanmin(self.signals_min[self.visible_channels])
            self.viewer.params['ylim_max'] = np.nanmax(self.signals_max[self.visible_channels])
        else:
            if scale_mode=='same_for_all':
                inv_scale =  max(self.signals_mad[self.visible_channels]) * spacing_factor
                if inv_scale == 0:
                    inv_scale = 1.
            elif scale_mode=='by_channel':
                inv_scale = self.signals_mad[self.visible_channels] * spacing_factor
                inv_scale[inv_scale==0.] = 1.
            gains[self.visible_channels] = np.ones(nb_visible, dtype=float) / inv_scale
            offsets[self.visible_channels] = np.arange(nb_visible)[::-1] - self.signals_med[self.visible_channels]*gains[self.visible_channels]
            self.viewer.params['ylim_min'] = -0.5
            self.viewer.params['ylim_max'] = nb_visible-0.5
        
        self.gains = gains
        self.offsets = offsets
        self.viewer.by_channel_params.blockSignals(False)

    def apply_ygain_zoom(self, factor_ratio):
        
        scale_mode = self.viewer.params['scale_mode']
        
        self.viewer.all_params.blockSignals(True)
        if scale_mode=='real_scale':
            ymin, ymax = self.viewer.params['ylim_min'], self.viewer.params['ylim_max']
            d = (ymax-ymin) * factor_ratio / 2.
            self.viewer.params['ylim_max'] = (ymin+ymax)/2. + d
            self.viewer.params['ylim_min'] = (ymin+ymax)/2. - d
        else :
            if not hasattr(self, 'self.signals_med'):
                self.estimate_median_mad()
            vis_offset = self.offsets + self.signals_med*self.gains
            self.gains = self.gains * factor_ratio
            #~ self.offsets = self.offsets + self.signals_med*self.gains * (1-factor_ratio)
            self.offsets = vis_offset - self.signals_med*self.gains
        self.viewer.all_params.blockSignals(False)
        
        self.viewer.refresh()
        
    def apply_xsize_zoom(self, xmove):
        factor = xmove/100.
        factor = max(factor, -0.999999999)
        factor = min(factor, 1)
        newsize = self.viewer.params['xsize']*(factor+1.)
        self.viewer.params['xsize'] = max(newsize, MIN_XSIZE)


default_params = [
    {'name': 'xsize', 'type': 'float', 'value': 3., 'step': 0.1},
    {'name': 'ylim_max', 'type': 'float', 'value': 10.},
    {'name': 'ylim_min', 'type': 'float', 'value': -10.},
    {'name': 'scale_mode', 'type': 'list', 'value': 'real_scale', 
        'values':['real_scale', 'same_for_all', 'by_channel'] },
    {'name': 'background_color', 'type': 'color', 'value': 'k'},
    {'name': 'refresh_interval', 'type': 'int', 'value': 100, 'limits':[5, 1000]},
    {'name': 'mode', 'type': 'list', 'value': 'scan', 'values': ['scan', 'scroll']},
    {'name': 'auto_decimate', 'type': 'bool', 'value': True},
    {'name': 'decimate', 'type': 'int', 'value': 1, 'limits': [1, None], },
    {'name': 'decimation_method', 'type': 'list', 'value': 'pure_decimate', 'values': ['pure_decimate', 'min_max', 'mean']},
    {'name': 'display_labels', 'type': 'bool', 'value': False},
    {'name': 'show_bottom_axis', 'type': 'bool', 'value': False},
    {'name': 'show_left_axis', 'type': 'bool', 'value': False},
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
    
    _ControllerClass = OscilloscopeController
    
    def __init__(self, **kargs):
        BaseOscilloscope.__init__(self, **kargs)
        

    def _configure(self, with_user_dialog=True, max_xsize = 60.):
        BaseOscilloscope._configure(self, with_user_dialog=with_user_dialog, max_xsize = max_xsize)

    def _initialize(self):
        BaseOscilloscope._initialize(self)
        
        if self.params_controller is not None:
            self.viewBox.gain_zoom.connect(self.params_controller.apply_ygain_zoom)
        self.viewBox.xsize_zoom.connect(self.apply_xsize_zoom)
            
        self.params.param('xsize').setLimits([2./self.sample_rate, self.max_xsize*.95])
        
        self.curves = []
        self.channel_labels = []
        for i in range(self.nb_channel):
            color = '#7FFF00'  # TODO
            curve = pg.PlotCurveItem(pen=color)
            self.plot.addItem(curve)
            self.curves.append(curve)
            txt = '{}: {}'.format(i, self.channel_names[i])
            label = pg.TextItem(txt, color=color, anchor=(0.5, 0.5), border=None, fill=pg.mkColor((128,128,128, 200)))
            self.plot.addItem(label)
            self.channel_labels.append(label)
        
        self.reset_curves_data()
    
    def _refresh(self):
        mode = self.params['mode']
        decimate = int(self.params['decimate'])
        gains = np.array([p['gain'] for p in self.by_channel_params.children()])
        offsets = np.array([p['offset'] for p in self.by_channel_params.children()])
        visibles = np.array([p['visible'] for p in self.by_channel_params.children()], dtype=bool)
        xsize = self.params['xsize'] 
        
        head = self._head
        if decimate>1:
            if self.params['decimation_method'] == 'min_max':
                head = head - head%(decimate*2)
            else:
                head = head - head%decimate
        
        full_arr = self.inputs['signals'].get_data(head-self.full_size, head, copy=False, join=True).T
        
        full_arr = full_arr.astype(float)
        
        if decimate>1:
            if self.params['decimation_method'] == 'pure_decimate':
                small_arr = full_arr[:, ::decimate].copy()
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
                
        self.plot.showAxis('left', self.params['show_left_axis'])
        self.plot.showAxis('bottom', self.params['show_bottom_axis'])

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
            if param.name()=='scale_mode':
                self.params_controller.compute_rescale()
    
    def gain_zoom(self, factor, selected=None):
        for i, p in enumerate(self.by_channel_params.children()):
            if selected is not None and not selected[i]: continue
            if self.all_mean is not None:
                p['offset'] = p['offset'] + self.all_mean[i]*p['gain'] - self.all_mean[i]*p['gain']*factor
            p['gain'] = p['gain']*factor
    
    def get_visible_chunk(self):
        head = self._head
        sigs = self.inputs['signals'].get_data(max(-1, head-self.full_size), head) # this ensure having at least one sample
        return sigs
        
    def auto_scale(self, spacing_factor=9.):
        self.params_controller.compute_rescale(spacing_factor=spacing_factor)
        self.refresh()

register_node_type(QOscilloscope)




