# -*- coding: utf-8 -*-
# Copyright (c) 2016, French National Center for Scientific Research (CNRS)
# Distributed under the (new) BSD License. See LICENSE for more info.

from pyqtgraph.Qt import QtCore, QtGui
import pyqtgraph as pg

import numpy as np


from .qoscilloscope import BaseOscilloscope, OscilloscopeController


class DigitalOscilloscope

class QDigitalOscilloscope(BaseOscilloscope):
    _input_specs = {'signals': dict(streamtype='signals')}
    
    _default_params =  [
                    {'name': 'ylim_max', 'type': 'float', 'value': 10.},
                    {'name': 'ylim_min', 'type': 'float', 'value': -10.},
                    {'name': 'background_color', 'type': 'color', 'value': 'k' },
                    {'name': 'refresh_interval', 'type': 'int', 'value': 100 , 'limits':[5, 1000]},
                    {'name': 'display_labels', 'type': 'bool', 'value': False},
                ]
    
    _default_by_channel_params =  [ 
                    {'name': 'visible', 'type': 'bool', 'value': True},
                ]
    
    #~ _ControllerClass = TriggeredOscilloscopeController
    
    def __init__(self, **kargs):
        BaseOscilloscope.__init__(self, **kargs)

    def _initialize(self):
        BaseOscilloscope._initialize(self)

    def _start(self):
        BaseOscilloscope._start(self)
        
    def _stop(self):
        BaseOscilloscope._stop(self)
    
    def _refresh(self):
        pass

    def on_param_change(self, params, changes):
        for param, change, data in changes:
            if change != 'value': continue
            #~ print param.name()
            #~ if param.name() in ['gain', 'offset']: 
                #~ self.redraw_stack()
            #~ if param.name()=='ylims':
                #~ continue
            #~ if param.name()=='visible':
                #~ c = self.by_channel_params.children().index(param.parent())
                #~ for curve in self.list_curves[c]:
                    #~ if data:
                        #~ curve.show()
                    #~ else:
                        #~ curve.hide()
            #~ if param.name()=='background_color':
                #~ self.graphicsview.setBackground(data)
            #~ if param.name()=='refresh_interval':
                #~ self.timer.setInterval(data)
            #~ if param.name() in ['left_sweep', 'right_sweep', 'stack_size']:
                #~ self.plotted_trig = -1
                #~ self.reset_curves_data()
            #~ if param.name() in [ 'channel','threshold','debounce_time','debounce_mode', 'front']:
                #~ continue

    def gain_zoom(self, factor, selected=None):
        for i, p in enumerate(self.by_channel_params.children()):
            if selected is not None and not selected[i]: continue
            if self.all_mean is not None:
                p['offset'] = p['offset'] + self.all_mean[i]*p['gain'] - self.all_mean[i]*p['gain']*factor
            p['gain'] = p['gain']*factor
    
    def get_visible_chunk(self):
        head = self._head
        sigs = self.inputs['signals'].get_data(head-self.full_size, head)
        return sigs
        
    def auto_scale(self):
        self.params_controller.compute_rescale()
        self.refresh()
