# -*- coding: utf-8 -*-
# Copyright (c) 2016, French National Center for Scientific Research (CNRS)
# Distributed under the (new) BSD License. See LICENSE for more info.

from pyqtgraph.Qt import QtCore, QtGui
import pyqtgraph as pg

import numpy as np
import weakref

from ..core import (WidgetNode, register_node_type, InputStream,
        ThreadPollInput, StreamConverter)

from .qoscilloscope import MyViewBox, BaseOscilloscope, QOscilloscope, OscilloscopeController


class OscilloscopeMultiPlotController(OscilloscopeController):
    def compute_rescale(self, spacing_factor=9.):
        self.viewer.by_channel_params.blockSignals(True)

        sigs = self.viewer.get_visible_chunk()
        self.signals_min = np.nanmin(sigs, axis=0)
        self.signals_max = np.nanmax(sigs, axis=0)
        
        for i in range(self.viewer.nb_channel):
            ylim_min = self.signals_min[i]
            ylim_max = self.signals_max[i]
            if ylim_max == ylim_min:
                # avoid flat zoom
                ylim_max += 1
                
            self.viewer.by_channel_params['ch{}'.format(i), 'ylim_min'] = ylim_min
            self.viewer.by_channel_params['ch{}'.format(i), 'ylim_max'] = ylim_max
        
        self.viewer.by_channel_params.blockSignals(False)

    def apply_ygain_zoom(self, factor_ratio):
        chan = self.viewer.viewBoxes.index(self.sender())
        
        self.viewer.all_params.blockSignals(True)
        
        ymin = self.viewer.by_channel_params['ch{}'.format(chan), 'ylim_min']
        ymax = self.viewer.by_channel_params['ch{}'.format(chan), 'ylim_max']
        
        d = (ymax-ymin) * factor_ratio / 2.
        self.viewer.by_channel_params['ch{}'.format(chan), 'ylim_max'] = (ymin+ymax)/2. + d
        self.viewer.by_channel_params['ch{}'.format(chan), 'ylim_min'] = (ymin+ymax)/2. - d
            
        self.viewer.all_params.blockSignals(False)

default_params = [
    {'name': 'xsize', 'type': 'float', 'value': 3., 'step': 0.1},
    {'name': 'background_color', 'type': 'color', 'value': 'k'},
    {'name': 'refresh_interval', 'type': 'int', 'value': 100, 'limits':[5, 1000]},
    {'name': 'mode', 'type': 'list', 'value': 'scan', 'values': ['scan', 'scroll']},
    {'name': 'auto_decimate', 'type': 'bool', 'value': True},
    {'name': 'decimate', 'type': 'int', 'value': 1, 'limits': [1, None], },
    {'name': 'decimation_method', 'type': 'list', 'value': 'pure_decimate', 'values': ['pure_decimate', 'min_max', 'mean']},
    {'name': 'display_labels', 'type': 'bool', 'value': False},
    {'name': 'show_bottom_axis', 'type': 'bool', 'value': True},
    {'name': 'show_left_axis', 'type': 'bool', 'value': True},
    ]

default_by_channel_params = [ 
    #~ {'name': 'gain', 'type': 'float', 'value': 1, 'step': 0.1},
    #~ {'name': 'offset', 'type': 'float', 'value': 0., 'step': 0.1},
    {'name': 'visible', 'type': 'bool', 'value': True},
    {'name': 'ylim_max', 'type': 'float', 'value': 10.},
    {'name': 'ylim_min', 'type': 'float', 'value': -10.},
    
    ]

class QOscilloscopeMultiPlot(BaseOscilloscope):
    _input_specs = {'signals': dict(streamtype='signals')}
    
    _default_params = default_params
    _default_by_channel_params = default_by_channel_params
    
    _ControllerClass = OscilloscopeMultiPlotController
    
    def __init__(self, **kargs):
        BaseOscilloscope.__init__(self, **kargs)
        

    def _configure(self, with_user_dialog=True, max_xsize = 60.):
        BaseOscilloscope._configure(self, with_user_dialog=with_user_dialog, max_xsize = max_xsize)

    def _initialize(self):
        
        BaseOscilloscope._initialize(self)
        
        # hack the BaseOscilloscope and change to multiplot
        
        
        self.multiplot = pg.GraphicsLayout()
        self.graphicsview.setCentralItem(self.multiplot)
        self.plots =[]
        self.viewBoxes = []
        for i in range(self.nb_channel):
            viewBox = MyViewBox()
            plot = self.multiplot.addPlot(row=i, col=0, viewBox=viewBox)
            plot.hideButtons()
            plot.showAxis('left', False)
            plot.showAxis('bottom', False)            
            self.plots.append(plot)
            self.viewBoxes.append(viewBox)
            
            if self.params_controller is not None:
                viewBox.gain_zoom.connect(self.params_controller.apply_ygain_zoom)
            viewBox.xsize_zoom.connect(self.apply_xsize_zoom)
            
        
        del self.plot
        
        if self.params_controller is not None:
            for viewBox in self.viewBoxes:
                viewBox.doubleclicked.connect(self.show_params_controller)
                viewBox.gain_zoom.connect(self.params_controller.apply_ygain_zoom)
            viewBox.xsize_zoom.connect(self.apply_xsize_zoom)
            
        self.params.param('xsize').setLimits([2./self.sample_rate, self.max_xsize*.95])
        
        self.curves = []
        self.channel_labels = []
        for i in range(self.nb_channel):
            color = '#7FFF00'  # TODO
            curve = pg.PlotCurveItem(pen=color)
            self.plots[i].addItem(curve)
            self.curves.append(curve)
            txt = '{}: {}'.format(i, self.channel_names[i])
            label = pg.TextItem(txt, color=color, anchor=(0.5, 0.5), border=None, fill=pg.mkColor((128,128,128, 200)))
            self.plots[i].addItem(label)
            self.channel_labels.append(label)
        
        self.reset_curves_data()
    
    def _refresh(self):
        mode = self.params['mode']
        decimate = int(self.params['decimate'])
        visibles = self.params_controller.visible_channels
        xsize = self.params['xsize'] 
        
        head = self._head
        if decimate>1:
            if self.params['decimation_method'] == 'min_max':
                head = head - head%(decimate*2)
            else:
                head = head - head%decimate
        
        full_arr = self.get_visible_chunk(head=head, limit_to_head_0=False).T
        
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
        
        for c, visible in enumerate(visibles):
            if visible:
                ylim_min = self.by_channel_params['ch{}'.format(c), 'ylim_min']
                ylim_max = self.by_channel_params['ch{}'.format(c), 'ylim_max']
                self.plots[c].setXRange(self.t_vect[0], self.t_vect[-1])
                self.plots[c].setYRange(ylim_min, ylim_max)
                self.plots[c].showAxis('left', self.params['show_left_axis'])
                self.plots[c].showAxis('bottom', self.params['show_bottom_axis'])
                self.plots[c].show()
                label = self.channel_labels[c]
                if self.params['display_labels']:
                    label.setPos(-self.params['xsize'], (ylim_min+ylim_max)/2)
                    label.setVisible(True)
                else:
                    label.setVisible(False)
            else:
                self.plots[c].hide()
    
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
    
    def get_visible_chunk(self, head=None, limit_to_head_0=True):
        if head is None:
            head = self._head
        if limit_to_head_0:
            sigs = self.inputs['signals'].get_data(max(-1, head-self.full_size), head, copy=False, join=True) # this ensure having at least one sample
        else:
            # get signal even before head=0
            sigs = self.inputs['signals'].get_data(head-self.full_size, head, copy=False, join=True)
        return sigs
        
    def auto_scale(self, spacing_factor=9.):
        self.params_controller.compute_rescale(spacing_factor=spacing_factor)
        self.refresh()

register_node_type(QOscilloscopeMultiPlot)
    