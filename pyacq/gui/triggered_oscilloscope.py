# -*- coding: utf-8 -*-

from PyQt4 import QtCore,QtGui
import pyqtgraph as pg
import zmq


from pyacq import AnalogTrigger


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
        
        self.paramGlobal.param('channel').setLimits([0, self.stream['nb_channel']])

        # Create curve list items
        self.list_curves = [ [ ] for i in range(self.stream['nb_channel']) ]
        self.recreate_stack()
        self.recreate_curves()
        
        kargs = { k: self.paramGlobal[k] for  k in ['channel', 'threshold', 'debounce_mode', 'debounce_time', 'front']}
        self.trigger = AnalogTrigger(stream = self.stream, autostart = False, callbacks = [ self.on_trigger], **kargs)
        
        self.start()
        
        self.threads_limit = [ ]
        self.vline = pg.InfiniteLine(pos=0, angle=90, pen='r')
        self.plot.addItem(self.vline)
        

    def start(self):
        self.trigger.start()
        BaseOscilloscope.start(self)

    def stop(self):
        BaseOscilloscope.stop(self)
        self.trigger.stop()
        for thread in self.threads_limit:
            thread.stop()
            thread.wait()
    
    def recreate_stack(self):
        n = self.stream['nb_channel']
        stack_size = self.paramGlobal['stack_size']
        left_sweep = self.paramGlobal['left_sweep']
        right_sweep = self.paramGlobal['right_sweep']
        sr = self.stream['sampling_rate']

        self.limit1 = l1 = int(left_sweep*sr)
        self.limit2 = l2 = int(right_sweep*sr)
        
        self.t_vect = np.arange(l2-l1)/sr+left_sweep
        self.stack = np.zeros((stack_size, n, l2-l1), dtype = self.stream.shared_array.dtype)
        self.stack_pos = 0
        
        self.total_trig = 0
        self.plotted_trig = 0
        
    
    def reset_stack(self):
        self.stack[:] = 0
        self.stack_pos = 0
        
        self.total_trig = 0
        self.plotted_trig = 0
    
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
                self.redraw_stack()
            if param.name()=='background_color':
                self.graphicsview.setBackground(data)
            if param.name()=='xsize':
                self.recreate_stack()
                self.recreate_curves()
                self.redraw_stack()
            if param.name()=='refresh_interval':
                self.timer.setInterval(data)
            if param.name()=='stack_size':
                self.recreate_stack()
                self.recreate_curves()
            if param.name() in ['left_sweep', 'right_sweep']:
                self.recreate_stack()
                self.recreate_curves()
            if param.name() in [ 'channel','threshold','debounce_time','debounce_mode', 'front']:
                kargs = {param.name() : data }
                self.trigger.set_params(**kargs)
    
    def redraw_stack(self):
        self.plotted_trig = max(self.total_trig - self.paramGlobal['stack_size'], 0)

    def on_trigger(self, pos):
        socket = self.context.socket(zmq.SUB)
        socket.setsockopt(zmq.SUBSCRIBE,'')
        socket.connect("tcp://localhost:{}".format(self.stream['port']))
        thread = WaitLimitThread(socket = socket, pos_limit = self.limit2+pos)
        thread.limit_reached.connect(self.on_limit_reached)
        self.threads_limit.append(thread)
        thread.start()
        
    def on_limit_reached(self, limit):
        self.threads_limit.remove(self.sender())
        
        head = limit%self.half_size+self.half_size
        tail = head - (self.limit2 - self.limit1)
        self.stack[self.stack_pos,:,:] = self.np_array[:, tail:head]
        
        self.stack_pos +=1
        self.stack_pos = self.stack_pos%self.paramGlobal['stack_size']
        self.total_trig += 1

    def refresh(self):
        stack_size = self.paramGlobal['stack_size'] 
        n = self.stream['nb_channel']
        gains = np.array([p['gain'] for p in self.paramChannels.children()])
        offsets = np.array([p['offset'] for p in self.paramChannels.children()])
        visibles = np.array([p['visible'] for p in self.paramChannels.children()], dtype = bool)
        
        if self.plotted_trig<self.total_trig-stack_size:
            self.plotted_trig = self.total_trig-stack_size
        
        while self.plotted_trig<self.total_trig:
            pos = self.plotted_trig%stack_size
            for c in range(n):
                data = self.stack[pos, c, :]*gains[c]+offsets[c]
                if visibles[c]:
                    self.list_curves[c][pos].setData(self.t_vect, data, antialias = False)
            self.plotted_trig += 1
        
        self.plot.setXRange( self.t_vect[0], self.t_vect[-1])
        ylims  =self.paramGlobal['ylims']
        self.plot.setYRange( *ylims )
    
    
    def autoestimate_scales(self):
        #TODO
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

    
    def auto_gain_and_offset(self, mode = 0, selected = None):
        #TODO
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
