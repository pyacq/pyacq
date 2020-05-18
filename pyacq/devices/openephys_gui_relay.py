# -*- coding: utf-8 -*-
# Copyright (c) 2016, French National Center for Scientific Research (CNRS)
# Distributed under the (new) BSD License. See LICENSE for more info.

import numpy as np

from ..core import Node, register_node_type
from pyqtgraph.Qt import QtCore, QtGui
from pyqtgraph.util.mutex import Mutex

import zmq
import json
from pprint import pprint



class OpenEphysGUIRelay(Node):
    """
    
    """
    _output_specs = {'signals': dict(streamtype='analogsignal', dtype='float32', transfermode='sharedmem') }

    def __init__(self, **kargs):
        Node.__init__(self, **kargs)

    def _configure(self, openephys_url='tcp://127.0.0.1:20000'):
        '''
        '''
        self.openephys_url = openephys_url
        
        print('configure', openephys_url)
        context = zmq.Context.instance()
        self.socket = context.socket(zmq.PAIR)
        #~ self.socket.linger = 1000  # don't let socket deadlock when exiting
        #~ self.socket.setsockopt(zmq.SUBSCRIBE, b'')
        self.socket.connect(openephys_url)

        self.socket.send(b'config')
        msg = self.socket.recv()
        self.stream_params = json.loads(msg.decode())
        pprint(self.stream_params)
        
        #~ self.stream_params = stream_params
        
        #~ self.nb_channel = 

        #~ self.outputs['signals'].spec['shape'] = (-1, self.nb_channel)
        #~ self.outputs['signals'].spec['sample_rate'] = self.sample_rate
        #~ self.outputs['signals'].spec['nb_channel'] = self.nb_channel
        #~ self.outputs['signals'].spec.update(stream_params)
        #~ self.outputs['signals'].spec.update(self.stream_params)
    
    def _initialize(self):
        pass

    def after_output_configure(self, outputname):
        if outputname == 'signals':
            self.outputs['signals'].params.update(self.stream_params)

    def _start(self):
        self.socket.send(b'start')
        msg = self.socket.recv()
        assert msg == b'ok'
        
    
    def _stop(self):
        self.socket.send(b'stop')
        msg = self.socket.recv()
        assert msg == b'ok'

    def _close(self):
        pass


register_node_type(OpenEphysGUIRelay)
