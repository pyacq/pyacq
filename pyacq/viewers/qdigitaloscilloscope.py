# -*- coding: utf-8 -*-
# Copyright (c) 2016, French National Center for Scientific Research (CNRS)
# Distributed under the (new) BSD License. See LICENSE for more info.

from pyqtgraph.Qt import QtCore, QtGui
import pyqtgraph as pg

import numpy as np


from .qoscilloscope import BaseOscilloscope, QOscilloscope, OscilloscopeController



class DigitalOscilloscopeController(OscilloscopeController):
    @property
    def visible_channels(self):
        visible = [self.viewer.by_channel_params['ch{}'.format(i), 'visible'] for i in range(self.viewer.nb_channel)]
        return np.array(visible, dtype='bool')

    @property
    def gains(self):
        return np.ones(self.viewer.nb_channel) * 0.8

    @property
    def offsets(self):
        visible_channels = self.visible_channels
        n = np.sum(visible_channels)
        offsets = np.zeros(self.viewer.nb_channel)
        for i, ind in enumerate(np.nonzero(visible_channels)[0]):
            offsets[ind] = n -1 - i
        return offsets

    def estimate_median_mad(self):
        pass
    
    def compute_rescale(self, spacing_factor=9.):
        self.viewer.by_channel_params.blockSignals(True)
        visible_channels = self.visible_channels
        n = np.sum(visible_channels)
        self.viewer.params['ylim_min']  = -.5
        self.viewer.params['ylim_max'] = n + .3
        self.viewer.by_channel_params.blockSignals(False)

    def apply_ygain_zoom(self, factor_ratio):
        pass


class QDigitalOscilloscope(QOscilloscope):
    _input_specs = {'signals': dict(streamtype='signals')}
    
    _default_params =  [
        {'name': 'xsize', 'type': 'float', 'value': 3., 'step': 0.1},
        {'name': 'ylim_max', 'type': 'float', 'value': 10.},
        {'name': 'ylim_min', 'type': 'float', 'value': -10.},
        {'name': 'background_color', 'type': 'color', 'value': 'k'},
        {'name': 'refresh_interval', 'type': 'int', 'value': 100, 'limits':[5, 1000]},
        {'name': 'mode', 'type': 'list', 'value': 'scan', 'limits': ['scan', 'scroll']},
        {'name': 'auto_decimate', 'type': 'bool', 'value': True},
        {'name': 'decimate', 'type': 'int', 'value': 1, 'limits': [1, None], },
        {'name': 'decimation_method', 'type': 'list', 'value': 'pure_decimate', 'limits': ['pure_decimate', 'min_max', 'mean']},
        {'name': 'display_labels', 'type': 'bool', 'value': True},
        {'name': 'show_bottom_axis', 'type': 'bool', 'value': False},
        {'name': 'show_left_axis', 'type': 'bool', 'value': False},
    ]
    
    _default_by_channel_params =  [
            {'name': 'visible', 'type': 'bool', 'value': True},
     ]
    
    _ControllerClass = DigitalOscilloscopeController
    

    def _check_nb_channel(self):
        shape1 = self.inputs['signals'].params['shape'][1]
        itemsize = np.dtype(self.inputs['signals'].params['dtype']).itemsize
        self.nb_channel = shape1 * itemsize * 8

    def _initialize(self):
        QOscilloscope._initialize(self)
        self.params_controller.compute_rescale()

    def get_visible_chunk(self, head=None, limit_to_head_0=True):
        if head is None:
            head = self._head
        if limit_to_head_0:
            raw_bits = self.inputs['signals'].get_data(max(-1, head-self.full_size), head, copy=False, join=True) # this ensure having at least one sample
        else:
            # get signal even before head=0
            raw_bits = self.inputs['signals'].get_data(head-self.full_size, head, copy=False, join=True)
        
        # treansform one bit to one uint8
        sigs = np.zeros((raw_bits.shape[0], self.nb_channel), dtype='uint8')
        for chan in range(self.nb_channel):
            b = chan//8
            mask = 1<<(chan%8)
            sigs[:, chan] =  (raw_bits[:,b] & mask)>0
        
        return sigs
