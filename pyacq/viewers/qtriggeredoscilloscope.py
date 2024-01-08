# -*- coding: utf-8 -*-
# Copyright (c) 2016, French National Center for Scientific Research (CNRS)
# Distributed under the (new) BSD License. See LICENSE for more info.

from pyqtgraph.Qt import QtCore, QtWidgets
import pyqtgraph as pg

import numpy as np


from .qoscilloscope import BaseOscilloscope, OscilloscopeController
from ..core import (register_node_type,  StreamConverter)
from ..dsp import AnalogTrigger, TriggerAccumulator



class TriggeredOscilloscopeController(OscilloscopeController):
    def __init__(self, parent=None, viewer=None):
        OscilloscopeController.__init__(self, parent=parent, viewer=viewer)


        self.tree_params2 = pg.parametertree.ParameterTree()
        self.tree_params2.setParameters(self.viewer.trigger.params, showTop=True)
        self.tree_params2.header().hide()
        self.v1.addWidget(self.tree_params2)

        self.tree_params3 = pg.parametertree.ParameterTree()
        self.tree_params3.setParameters(self.viewer.triggeraccumulator.params, showTop=True)
        self.tree_params3.header().hide()
        self.v1.addWidget(self.tree_params3)
        

class QTriggeredOscilloscope(BaseOscilloscope):
    _input_specs = {'signals': dict(streamtype='signals')}
    
    _default_params =  [
                    {'name': 'xsize', 'type': 'float', 'value': 3., 'step': 0.1},
                    {'name': 'ylim_max', 'type': 'float', 'value': 10.},
                    {'name': 'ylim_min', 'type': 'float', 'value': -10.},
                    {'name': 'background_color', 'type': 'color', 'value': 'k' },
                    {'name': 'refresh_interval', 'type': 'int', 'value': 100 , 'limits':[5, 1000]},
                    {'name': 'auto_decimate', 'type': 'bool', 'value': True},
                    {'name': 'decimate', 'type': 'int', 'value': 1, 'limits': [1, None], },
                    {'name': 'decimation_method', 'type': 'list', 'value': 'pure_decimate', 'limits': ['pure_decimate', 'min_max', 'mean']},
                    {'name': 'display_labels', 'type': 'bool', 'value': False},
                    {'name': 'scale_mode', 'type': 'list', 'value': 'real_scale', 
                        'limits':['real_scale', 'same_for_all', 'by_channel'] },
                    
                ]
    
    _default_by_channel_params =  [ 
                    {'name': 'gain', 'type': 'float', 'value': 1, 'step': 0.1},
                    {'name': 'offset', 'type': 'float', 'value': 0., 'step': 0.1},
                    {'name': 'visible', 'type': 'bool', 'value': True},
                ]
    
    _ControllerClass = TriggeredOscilloscopeController
    
    def __init__(self, **kargs):
        BaseOscilloscope.__init__(self, **kargs)

        h = QtWidgets.QHBoxLayout()
        self.layout.addLayout(h)
        self.but_startstop = QtWidgets.QPushButton('Start/Stop', checkable = True, checked = True)
        h.addWidget(self.but_startstop)
        self.but_startstop.toggled.connect(self.start_or_stop_trigger)
        but = QtWidgets.QPushButton('Reset')
        but.clicked.connect(self.reset_stack)
        h.addWidget(but)
        self.label_count = QtWidgets.QLabel('Nb events:')
        h.addWidget(self.label_count)
        h.addStretch()
        
        self.viewBox.gain_zoom.connect(self.gain_zoom)
        
        self.trigger = AnalogTrigger()
        self.triggeraccumulator = TriggerAccumulator()

    def _initialize(self):
        BaseOscilloscope._initialize(self)
        
        #create a trigger
        
        self.trigger.configure()
        self.trigger.input.connect(self.input.params)
        self.trigger.output.configure(protocol='inproc', transfermode='plaindata')
        self.trigger.initialize()
        
        #create a triggeraccumulator
        
        self.triggeraccumulator.configure(max_stack_size = np.inf)
        self.triggeraccumulator.inputs['signals'].connect(self.input.params)
        self.triggeraccumulator.inputs['events'].connect(self.trigger.output)
        self.triggeraccumulator.initialize()
        
        self.trigger.params.sigTreeStateChanged.connect(self.on_param_change)
        self.triggeraccumulator.params.sigTreeStateChanged.connect(self.on_param_change)
        
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
        
        self.vline = pg.InfiniteLine(pos=0, angle=90, pen='r')
        self.plot.addItem(self.vline)
        
        self.list_curves = [ [ ] for i in range(self.nb_channel) ]
        
        self.recreate_stack()
        self.reset_curves_data()
        
        
    
    def _start(self):
        BaseOscilloscope._start(self)
        self.trigger.start()
        self.triggeraccumulator.start()
        
    def _stop(self):
        BaseOscilloscope._stop(self)
        if self.trigger.running():
            self.trigger.stop()
        if self.triggeraccumulator.running():
            self.triggeraccumulator.stop()

    def start_or_stop_trigger(self, state):
        if state:
            self.trigger.start()
            self.triggeraccumulator.start()
        else:
            self.trigger.stop()
            self.triggeraccumulator.stop()

    def recreate_stack(self):
        self.triggeraccumulator.recreate_stack()
        self.plotted_trig = 0
        
    def reset_stack(self):
        self.triggeraccumulator.reset_stack()
        self.plotted_trig = -1
        stack_size = self.triggeraccumulator.params['stack_size']
        for c in range(self.nb_channel):
            for pos in range(stack_size):
                self.list_curves[c][pos].setData(self.triggeraccumulator.t_vect, np.zeros(self.triggeraccumulator.t_vect.shape), antialias = False)
        self._refresh()
    
    def _refresh(self):
        stack_size = self.triggeraccumulator.params['stack_size'] 
        
        #~ gains = np.array([p['gain'] for p in self.by_channel_params.children()])
        #~ offsets = np.array([p['offset'] for p in self.by_channel_params.children()])
        #~ visibles = np.array([p['visible'] for p in self.by_channel_params.children()], dtype=bool)
        
        gains = self.params_controller.gains
        offsets = self.params_controller.offsets
        visibles = self.params_controller.visible_channels

        
        
        if self.plotted_trig<self.triggeraccumulator.total_trig-stack_size:
            self.plotted_trig = self.triggeraccumulator.total_trig-stack_size
        
        while self.plotted_trig<self.triggeraccumulator.total_trig:
            pos = self.plotted_trig%stack_size
            for c in range(self.nb_channel):
                data = self.triggeraccumulator.stack[pos, c, :]*gains[c]+offsets[c]
                if visibles[c]:
                    self.list_curves[c][pos].setData(self.triggeraccumulator.t_vect, data, antialias = False)
            self.plotted_trig += 1
        
        self.plot.setXRange( self.triggeraccumulator.t_vect[0], self.triggeraccumulator.t_vect[-1])
        self.plot.setYRange(self.params['ylim_min'], self.params['ylim_max'])
        
        self.label_count.setText('Nb events: {}'.format(self.triggeraccumulator.total_trig))

        for c, visible in enumerate(visibles):
            label = self.channel_labels[c]
            if visible and self.params['display_labels']:
                if self.all_mean is not None:
                    label.setPos(self.triggeraccumulator.params['left_sweep'], self.all_mean[c]*gains[c]+offsets[c])
                else:
                    label.setPos(self.triggeraccumulator.params['left_sweep'], offsets[c])
                label.setVisible(True)
            else:
                label.setVisible(False)
    
    
    def on_param_change(self, params, changes):
        for param, change, data in changes:
            if change != 'value': continue
            #~ print param.name()
            if param.name() in ['gain', 'offset']: 
                self.redraw_stack()
            if param.name()=='ylims':
                continue
            if param.name()=='visible':
                c = self.by_channel_params.children().index(param.parent())
                for curve in self.list_curves[c]:
                    if data:
                        curve.show()
                    else:
                        curve.hide()
            if param.name()=='background_color':
                self.graphicsview.setBackground(data)
            if param.name()=='refresh_interval':
                self.timer.setInterval(data)
            if param.name() in ['left_sweep', 'right_sweep', 'stack_size']:
                self.plotted_trig = -1
                self.reset_curves_data()
            if param.name() in [ 'channel','threshold','debounce_time','debounce_mode', 'front']:
                continue

    def redraw_stack(self):
        self.plotted_trig = max(self.triggeraccumulator.total_trig - self.triggeraccumulator.params['stack_size'], 0)


    def reset_curves_data(self):
        stack_size = self.triggeraccumulator.params['stack_size']
        # delete olds
        for i,curves in enumerate(self.list_curves):
            for curve in curves:
                self.plot.removeItem(curve)
        
        self.list_curves = [ ]
        for i in range(self.nb_channel):
            curves = [ ]
            for j in range(stack_size):
                #~ color = self.by_channel_params.children()[i]['color'] #TODO
                color = '#7FFF00'  # TODO
                curve = pg.PlotCurveItem(pen = color)
                self.plot.addItem(curve)
                curves.append(curve)
            self.list_curves.append(curves)
    
    def gain_zoom(self, factor, selected=None):
        for i, p in enumerate(self.by_channel_params.children()):
            if selected is not None and not selected[i]: continue
            if self.all_mean is not None:
                p['offset'] = p['offset'] + self.all_mean[i]*p['gain'] - self.all_mean[i]*p['gain']*factor
            p['gain'] = p['gain']*factor
    
    def get_visible_chunk(self):
        stack_size = self.triggeraccumulator.params['stack_size'] 
        pos = self.plotted_trig%stack_size
        sigs = self.triggeraccumulator.stack[pos, :, :].T
        return sigs
        
    def auto_scale(self, spacing_factor=9.):
        self.params_controller.compute_rescale(spacing_factor=spacing_factor)
        self.refresh()
    
    #~ def estimate_decimate(self, nb_point=4000):
        #~ pass

    #~ def autoestimate_scales(self):
        #~ self.all_sd = np.array([np.std(self.triggeraccumulator.stack[:,i,:]) for i in range(self.nb_channel)])
        #~ self.all_mean = np.array([np.median(self.triggeraccumulator.stack[:,i,:]) for i in range(self.nb_channel)])
        #~ return self.all_mean, self.all_sd
    
    #~ def auto_gain_and_offset(self, mode=0, visibles=None):
        #~ """
        #~ mode = 0, 1, 2
        #~ """
        #~ if visibles is None:
            #~ visibles = np.ones(self.nb_channel, dtype=bool)
        
        #~ n = np.sum(visibles)
        #~ if n==0: return
        
        #~ av, sd = self.autoestimate_scales()
        #~ if av is None: return
        
        #~ if mode==0:
            #~ ylim_min, ylim_max = np.min(av[visibles]-3*sd[visibles]), np.max(av[visibles]+3*sd[visibles]) 
            #~ gains = np.ones(self.nb_channel, dtype=float)
            #~ offsets = np.zeros(self.nb_channel, dtype=float)
        #~ elif mode in [1, 2]:
            #~ ylim_min, ylim_max = -.5, n-.5 
            #~ gains = np.ones(self.nb_channel, dtype=float)
            #~ if mode==1 and max(sd[visibles])!=0:
                #~ gains = np.ones(self.nb_channel, dtype=float) * 1./(6.*max(sd[visibles]))
            #~ elif mode==2:
                #~ gains[sd!=0] = 1./(6.*sd[sd!=0])
            #~ offsets = np.zeros(self.nb_channel, dtype=float)
            #~ offsets[visibles] = range(n)[::-1] - av[visibles]*gains[visibles]
        
        #~ # apply
        #~ for i,param in enumerate(self.by_channel_params.children()):
            #~ param['gain'] = gains[i]
            #~ param['offset'] = offsets[i]
            #~ param['visible'] = visibles[i]
        #~ self.params['ylim_min'] = ylim_min
        #~ self.params['ylim_max'] = ylim_max


register_node_type(QTriggeredOscilloscope)