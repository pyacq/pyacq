# -*- coding: utf-8 -*-

from PyQt4 import QtCore,QtGui
import pyqtgraph as pg
import zmq


from pyacq import AnalogTrigger
from ..processing import StackedChunkOnTrigger

from .oscilloscope import BaseOscilloscope
from .guiutil import *
from .multichannelparam import MultiChannelParam
from .tools import WaitLimitThread



import time

from matplotlib.cm import get_cmap
from matplotlib.colors import ColorConverter

param_global = [
    {'name': 'left_sweep', 'type': 'float', 'value': -1., 'step': 0.1,'suffix': 's', 'siPrefix': True},
    {'name': 'right_sweep', 'type': 'float', 'value': 1., 'step': 0.1, 'suffix': 's', 'siPrefix': True},
    
    { 'name' : 'stack_size', 'type' :'int', 'value' : 1,  'limits':[1,np.inf] },
    
    { 'name' : 'channel', 'type' :'int', 'value' : 0,  'limits':[0,np.inf] },
    { 'name' : 'threshold', 'type' :'float', 'value' : 0.25 },
    { 'name' : 'front', 'type' :'list', 'values' : ['+', '-', ] },
    { 'name' : 'debounce_time', 'type' :'float', 'value' : 0.05, 'limits' : [0, np.inf], 'step' : 0.001 , 'suffix': 's', 'siPrefix': True },
    { 'name' : 'debounce_mode', 'type' :'list', 'values' : [ 'no-debounce', 'after-stable' , 'before-stable' ] },
    
    
    {'name': 'ylims', 'type': 'range', 'value': [-10., 10.] },
    {'name': 'background_color', 'type': 'color', 'value': 'k' },
    {'name': 'refresh_interval', 'type': 'int', 'value': 100 , 'limits':[5, 1000]},
    ]

param_by_channel = [ 
    {'name': 'color', 'type': 'color', 'value': '#7FFF00'},
    {'name': 'gain', 'type': 'float', 'value': 1, 'step': 0.1},
    {'name': 'offset', 'type': 'float', 'value': 0., 'step': 0.1},
    {'name': 'visible', 'type': 'bool', 'value': True},
    ]


class TriggeredOscilloscope(BaseOscilloscope):
    _param_global =param_global
    _param_by_channel = param_by_channel
    
    def __init__(self, stream = None, parent = None,):
        BaseOscilloscope.__init__(self, stream = stream, parent = parent,)
        h = QtGui.QHBoxLayout()
        self.mainlayout.addLayout(h)
        
        self.but_startstop = QtGui.QPushButton('Start/Stop', checkable = True, checked = True)
        h.addWidget(self.but_startstop)
        self.but_startstop.toggled.connect(self.start_or_stop_trigger)
        but = QtGui.QPushButton('Reset')
        but.clicked.connect(self.reset_stack)
        h.addWidget(but)
        self.label_count = QtGui.QLabel('Nb events:')
        h.addWidget(self.label_count)
        h.addStretch()
        
        
        self.paramGlobal.param('channel').setLimits([0, self.stream['nb_channel']-1])

        # Create curve list items
        self.list_curves = [ [ ] for i in range(self.stream['nb_channel']) ]
        
        self.stackedchunk = StackedChunkOnTrigger(stream = stream, parent = self)
        
        self.recreate_stack()
        self.recreate_curves()
        
        kargs = { k: self.paramGlobal[k] for  k in ['channel', 'threshold', 'debounce_mode', 'debounce_time', 'front']}
        self.trigger = AnalogTrigger(stream = self.stream, autostart = False, callbacks = [ self.on_trigger], **kargs)
        
        self.start()
        
        self.vline = pg.InfiniteLine(pos=0, angle=90, pen='r')
        self.plot.addItem(self.vline)
        

    def start(self):
        self.trigger.start()
        BaseOscilloscope.start(self)

    def stop(self):
        BaseOscilloscope.stop(self)
        if self.trigger.running:
            self.trigger.stop()
        for thread in self.stackedchunk.threads_limit:
            thread.stop()
            thread.wait()
    
    def start_or_stop_trigger(self, state):
        if state:
            self.trigger.start()
        else:
            self.trigger.stop()
    
    
    def recreate_stack(self):
        self.stackedchunk.recreate_stack()
        self.plotted_trig = 0
        
    def reset_stack(self):
        self.stackedchunk.reset_stack()
        self.plotted_trig = -1
    
    def recreate_curves(self):
        n = self.stream['nb_channel']
        stack_size = self.paramGlobal['stack_size']
        # delete olds
        for i,curves in enumerate(self.list_curves):
            for curve in curves:
                self.plot.removeItem(curve)
        
        self.list_curves = [ ]
        for i in range(n):
            curves = [ ]
            for j in range(stack_size):
                color = self.paramChannels.children()[i]['color']
                curve = pg.PlotCurveItem(pen = color)
                self.plot.addItem(curve)
                curves.append(curve)
            self.list_curves.append(curves)

    
    def on_param_change(self, params, changes):
        for param, change, data in changes:
            if change != 'value': continue
            #~ print param.name()
            if param.name() in ['gain', 'offset']: 
                self.redraw_stack()
            if param.name()=='ylims':
                continue
            if param.name()=='visible':
                c = self.paramChannels.children().index(param.parent())
                for curve in self.list_curves[c]:
                    if data:
                        curve.show()
                    else:
                        curve.hide()
            if param.name()=='color':
                i = self.paramChannels.children().index(param.parent())
                c = self.paramChannels.children().index(param.parent())
                for curve in self.list_curves[c]:
                    pen = pg.mkPen(color = data)
                    curve.setPen(pen)
                #~ self.redraw_stack()
            if param.name()=='background_color':
                self.graphicsview.setBackground(data)
            if param.name()=='xsize':
                self.recreate_stack()
                self.recreate_curves()
                self.redraw_stack()
            if param.name()=='refresh_interval':
                self.timer.setInterval(data)
            if param.name() in ['left_sweep', 'right_sweep', 'stack_size']:
                self.stackedchunk.allParams[param.name()] = data
                self.plotted_trig = -1
                #~ self.recreate_stack()
                self.recreate_curves()
            if param.name() in [ 'channel','threshold','debounce_time','debounce_mode', 'front']:
                kargs = {param.name() : data }
                self.trigger.set_params(**kargs)
    
    def redraw_stack(self):
        self.plotted_trig = max(self.stackedchunk.total_trig - self.paramGlobal['stack_size'], 0)

    def on_trigger(self, pos):
        self.stackedchunk.on_trigger(pos)
        
        #~ socket = self.context.socket(zmq.SUB)
        #~ socket.setsockopt(zmq.SUBSCRIBE,'')
        #~ socket.connect("tcp://localhost:{}".format(self.stream['port']))
        #~ thread = WaitLimitThread(socket = socket, pos_limit = self.limit2+pos)
        #~ thread.limit_reached.connect(self.on_limit_reached)
        #~ self.threads_limit.append(thread)
        #~ thread.start()
        
    #~ def on_limit_reached(self, limit):
        #~ self.threads_limit.remove(self.sender())
        
        #~ head = limit%self.half_size+self.half_size
        #~ tail = head - (self.limit2 - self.limit1)
        #~ self.stack[self.stack_pos,:,:] = self.np_array[:, tail:head]
        
        #~ self.stack_pos +=1
        #~ self.stack_pos = self.stack_pos%self.paramGlobal['stack_size']
        #~ self.total_trig += 1

    def refresh(self):
        stack_size = self.paramGlobal['stack_size'] 
        n = self.stream['nb_channel']
        gains = np.array([p['gain'] for p in self.paramChannels.children()])
        offsets = np.array([p['offset'] for p in self.paramChannels.children()])
        visibles = np.array([p['visible'] for p in self.paramChannels.children()], dtype = bool)
        
        #~ if self.plotted_trig<self.total_trig-stack_size:
            #~ self.plotted_trig = self.total_trig-stack_size

        if self.plotted_trig<self.stackedchunk.total_trig-stack_size:
            self.plotted_trig = self.stackedchunk.total_trig-stack_size
        
        
        #~ while self.plotted_trig<self.total_trig:
        while self.plotted_trig<self.stackedchunk.total_trig:
            pos = self.plotted_trig%stack_size
            for c in range(n):
                #~ data = self.stack[pos, c, :]*gains[c]+offsets[c]
                data = self.stackedchunk.stack[pos, c, :]*gains[c]+offsets[c]
                if visibles[c]:
                    self.list_curves[c][pos].setData(self.stackedchunk.t_vect, data, antialias = False)
            self.plotted_trig += 1
        
        self.plot.setXRange( self.stackedchunk.t_vect[0], self.stackedchunk.t_vect[-1])
        ylims  =self.paramGlobal['ylims']
        self.plot.setYRange( *ylims )
        
        self.label_count.setText('Nb events: {}'.format(self.stackedchunk.total_trig))
    
    
    def autoestimate_scales(self):
        
        
        n = self.stream['nb_channel']
        #~ self.all_mean =  np.array([ np.mean(self.np_array[i,tail:head]) for i in range(n) ])
        self.all_sd = np.array([ np.std(self.stackedchunk.stack[:,i,:]) for i in range(n) ])
        # better than std and mean
        self.all_mean = np.array([ np.median(self.stackedchunk.stack[:,i,:]) for i in range(n) ])
        #~ self.all_sd=  np.array([ np.median(np.abs(self.np_array[i,:tail:head]-self.all_mean[i])/.6745) for i in range(n) ])
        #~ print self.all_mean, self.all_sd
        return self.all_mean, self.all_sd

    


