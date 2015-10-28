from pyqtgraph.Qt import QtCore, QtGui
import pyqtgraph as pg

import numpy as np


from .qoscilloscope import MyViewBox, BaseOscilloscope
from ..core import (register_node_type,  StreamConverter)


class QTriggeredOscilloscope(BaseOscilloscope):
    _input_specs = {'signals': dict(streamtype='signals')}
    
    _default_params =  [
                    {'name': 'ylims', 'type': 'range', 'value': [-10., 10.] },
                    {'name': 'background_color', 'type': 'color', 'value': 'k' },
                    {'name': 'refresh_interval', 'type': 'int', 'value': 100 , 'limits':[5, 1000]},
                ]
    
    _default_by_channel_params =  [ 
                    {'name': 'gain', 'type': 'float', 'value': 1, 'step': 0.1},
                    {'name': 'offset', 'type': 'float', 'value': 0., 'step': 0.1},
                    {'name': 'visible', 'type': 'bool', 'value': True},
                ]
    
    def __init__(self, **kargs):
        BaseOscilloscope.__init__(self, **kargs)

        h = QtGui.QHBoxLayout()
        self.layout.addLayout(h)
        self.but_startstop = QtGui.QPushButton('Start/Stop', checkable = True, checked = True)
        h.addWidget(self.but_startstop)
        self.but_startstop.toggled.connect(self.start_or_stop_trigger)
        but = QtGui.QPushButton('Reset')
        but.clicked.connect(self.reset_stack)
        h.addWidget(but)
        self.label_count = QtGui.QLabel('Nb events:')
        h.addWidget(self.label_count)
        h.addStretch()
        
        self.viewBox.gain_zoom.connect(self.gain_zoom)

    def _initialize(self):
        BaseOscilloscope._initialize(self)
        
        #create a trigger
        self.trigger = AnalogTrigger()
        self.trigger.configure()
        self.trigger.input.connect(self.input_proxy.params)
        self.trigger.output.configure(protocol='inproc', transfermode='plaindata')
        self.trigger.initialize()
        
        #create a triggeraccumulator
        self.triggeraccumulator = TriggerAccumulator()
        self.triggeraccumulator.configure(max_stack_size = np.inf)
        self.triggeraccumulator.inputs['signals'].connect(self.input_proxy.params)
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
                self.list_curves[c][pos].setData(self.stackedchunk.t_vect, np.zeros(self.stackedchunk.t_vect.shape), antialias = False)
        self._refresh()
    
    def _refresh(self):
        pass
    
    def on_param_change(self, params, changes):
        #TODO
        pass

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
                color = self.paramChannels.children()[i]['color']
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
    
    
    def autoestimate_scales(self):
        if self._head is None:
            return None, None
        head = self._head
        sr = self.input.params['sample_rate']
        xsize = self.params['xsize'] 
        np_arr = self.proxy_input.get_array_slice(head,self.full_size)
        self.all_sd = np.std(np_arr, axis=1)
        # self.all_mean = np.mean(np_arr, axis = 1)
        self.all_mean = np.median(np_arr, axis=1)
        return self.all_mean, self.all_sd

    def auto_gain_and_offset(self, mode=0, visibles=None):
        """
        mode = 0, 1, 2
        """
        if visibles is None:
            visibles = np.ones(self.nb_channel, dtype=bool)
        
        n = np.sum(visibles)
        if n==0: return
        
        av, sd = self.autoestimate_scales()
        if av is None: return
        
        if mode==0:
            ylim_min, ylim_max = np.min(av[visibles]-3*sd[visibles]), np.max(av[visibles]+3*sd[visibles]) 
            gains = np.ones(self.nb_channel, dtype=float)
            offsets = np.zeros(self.nb_channel, dtype=float)
        elif mode in [1, 2]:
            ylim_min, ylim_max = -.5, n-.5 
            gains = np.ones(self.nb_channel, dtype=float)
            if mode==1 and max(sd[visibles])!=0:
                gains = np.ones(self.nb_channel, dtype=float) * 1./(6.*max(sd[visibles]))
            elif mode==2:
                gains[sd!=0] = 1./(6.*sd[sd!=0])
            offsets = np.zeros(self.nb_channel, dtype=float)
            offsets[visibles] = range(n)[::-1] - av[visibles]*gains[visibles]
        
        # apply
        for i,param in enumerate(self.by_channel_params.children()):
            param['gain'] = gains[i]
            param['offset'] = offsets[i]
            param['visible'] = visibles[i]
        self.params['ylim_min'] = ylim_min
        self.params['ylim_max'] = ylim_max


register_node_type(QTriggeredOscilloscope)