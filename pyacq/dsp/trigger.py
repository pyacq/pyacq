# -*- coding: utf-8 -*-
# Copyright (c) 2016, French National Center for Scientific Research (CNRS)
# Distributed under the (new) BSD License. See LICENSE for more info.

from pyqtgraph.Qt import QtCore
import pyqtgraph as pg
import weakref
import numpy as np

from ..core import (Node, register_node_type, ThreadPollInput, StreamConverter)



class TriggerThread(ThreadPollInput):
    new_triggers = QtCore.pyqtSignal(object)
    
    def __init__(self, input_stream, output_stream, timeout = 200, parent = None, emit_qt_signal=False):
        ThreadPollInput.__init__(self, input_stream, timeout = timeout, return_data=None, parent = parent)
        self.output_stream = weakref.ref(output_stream)
        
        self.emit_qt_signal = emit_qt_signal
        
        self.sample_rate = input_stream.params['sample_rate']
        self.last_pos = None
        self.n = 0
    
    def process_data(self, pos, data):
        if self.last_pos is None:
            self.last_pos = pos
        
        db = int(self.debounce_time*self.sample_rate)
        
        new = pos - self.last_pos
        if new<2: return
        
        if self.debounce_mode == 'no-debounce':
            newbuf = self.get_buffer_from_channel(pos, new)
            if newbuf is None: return
            sig1 = newbuf[:-1]
            sig2 = newbuf[1:]
        elif self.debounce_mode == 'after-stable':
            if new-db<2: return
            newbuf = self.get_buffer_from_channel(pos, new)
            if newbuf is None: return
            sig1 = newbuf[:-1-db]
            sig2 = newbuf[1:-db]
            pos -= db
        elif self.debounce_mode == 'before-stable':
            if new-2*db<2: return
            newbuf = self.get_buffer_from_channel(pos, new+db)
            if newbuf is None: return
            sig1 = newbuf[db:-1-2*db]
            sig2 = newbuf[db+1:-2*db]
            pos -= db*2
        
        if self.front == '+':
            crossings,  = np.where( (sig1 <= self.threshold) & ( sig2>self.threshold) )
        elif self.front == '-':
            crossings,  = np.where( (sig1 >= self.threshold) & ( sig2<self.threshold) )
        crossings +=1
        
        if self.debounce_mode == 'no-debounce':
            pass
        elif self.debounce_mode == 'after-stable':
            if self.front == '+':
                for i, crossing in enumerate(crossings):
                    if np.any(newbuf[crossing:crossing+db]<self.threshold):
                        crossings[i] = -1
            elif self.front == '-':
                for i, crossing in enumerate(crossings):
                    if np.any(newbuf[crossing:crossing+db]>self.threshold):
                        crossings[i] = -1
            crossings = crossings[crossings != -1]
        elif self.debounce_mode == 'before-stable':
            if self.front == '+':
                for i, crossing in enumerate(crossings+db):
                    if crossing == -1: continue
                    if np.any(newbuf[crossing+db:crossing+db*2]<self.threshold) or np.any(newbuf[crossing-db:crossing]>self.threshold):
                        crossings[i] = -1
            elif self.front == '-':
                for i, crossing in enumerate(crossings+db):
                    if crossing == -1: continue
                    if np.any(newbuf[crossing+db:crossing+db*2]>self.threshold) or np.any(newbuf[crossing-db:crossing]<self.threshold):
                        crossings[i] = -1
            crossings = crossings[crossings != -1]
        if crossings.size>0:
            self.n += crossings.size
            crossings += self.last_pos
            self.output_stream().send(crossings.astype('int64'), index=self.n)
            if self.emit_qt_signal:
                self.new_triggers.emit(crossings)

        
        self.last_pos = pos-1
    
    def change_params(self, params):
        for p in  params.children():
            setattr(self, p.name(), p.value())


class AnalogTriggerThread(TriggerThread):
    def get_buffer_from_channel(self, index, length):
        return self.input_stream().get_data(index-length, index)[:, self.channel, ]


class DigitalTriggerThread(TriggerThread):
    def get_buffer_from_channel(self, index, length):
        return self.input_stream().get_data(index-length, index)[:, self.b] & self.mask
    
    def change_params(self, params):
        TriggerThread.change_params(self, params)
        dt = np.dtype(self.input_stream().params['dtype'])
        self.b = self.channel//dt.itemsize
        self.mask = 1<<(self.channel%dt.itemsize)


class TriggerBase(Node,  QtCore.QObject):
    _input_specs = {'signals' : dict(streamtype = 'signals')}
    _output_specs = {'events' : dict(streamtype = 'events', dtype ='int64', shape = (-1, ))}
    
    _default_params = [
                        {'name': 'channel', 'type': 'int', 'value': 0},
                        {'name': 'threshold', 'type': 'float', 'value': 0.},
                        {'name': 'front', 'type': 'list', 'value': '+' , 'values' : ['+', '-'] },
                        {'name': 'debounce_mode', 'type': 'list', 'value': 'no-debounce' ,
                                            'values' : ['no-debounce', 'after-stable', 'before-stable'] },
                        {'name': 'debounce_time', 'type': 'float', 'value': 0.01},
                ]
    
    new_params = QtCore.Signal(object)
    
    def __init__(self, parent = None, **kargs):
        QtCore.QObject.__init__(self, parent)
        Node.__init__(self, **kargs)
        self.params = pg.parametertree.Parameter.create( name='Trigger options',
                                                    type='group', children =self._default_params)
    
    def _configure(self, max_size=2., emit_qt_signal=False):
        self.max_size = max_size
        self.params.sigTreeStateChanged.connect(self.on_params_change)
        self.emit_qt_signal = emit_qt_signal

    def after_input_connect(self, inputname):
        self.nb_channel = self.input.params['shape'][1]
        self.params.param('channel').setLimits([0, self.nb_channel-1])

    def _initialize(self):
        buf_size = int(self.input.params['sample_rate'] * self.max_size)
        self.input.set_buffer(size=buf_size, axisorder=[1,0], double=True)
        
        self.thread = self._TriggerThread(self.input, self.output, emit_qt_signal=self.emit_qt_signal)
        self.thread.change_params(self.params)
        self.new_params.connect(self.thread.change_params)
        
    
    def _start(self):
        self.thread.last_pos = None
        self.thread.start()
    
    def _stop(self):
        self.thread.stop()
        self.thread.wait()
    
    def _close(self):
        pass
    
    def on_params_change(self):
        self.new_params.emit(self.params)


class AnalogTrigger(TriggerBase):
    """
    No so efficient but quite robust trigger on analogsignal.
    
    This act like a standart trigger with a threshold and a front.
    The channel can be selected among all.
    
    All params can be set online via AnalogTrigger.params['XXX'] = ...
    
    The main feature is the **debounce mode** combinated with **debounce_time**:
      * **'no-debounce'** all crossing threshold is a trigger
      * **'after-stable'**  when interval between a series of triggers is too short, the **lastet one** is taken is account.
      * **'before-stable'** when interval between a series of triggers is too short, the **first one** is taken is account.
    
    
    """
    _TriggerThread = AnalogTriggerThread
    def check_input_specs(self):
        pass #TODO check that stream is analogsignal

register_node_type(AnalogTrigger)

class DigitalTrigger(TriggerBase):
    _TriggerThread = DigitalTriggerThread
    def check_input_specs(self):
        pass #TODO check that stream is digital

register_node_type(DigitalTrigger)
