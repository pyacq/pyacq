# -*- coding: utf-8 -*-
# Copyright (c) 2016, French National Center for Scientific Research (CNRS)
# Distributed under the (new) BSD License. See LICENSE for more info.

import json

import zmq

from ..core import Node, register_node_type, InputStream


class OpenEphysGUIRelay(Node):
    """
    
    """
    _output_specs = {'signals': dict(streamtype='analogsignal', dtype='float32', transfermode='sharedmem')}

    def __init__(self, **kargs):
        Node.__init__(self, **kargs)

    def _configure(self, openephys_url='tcp://127.0.0.1:20000'):
        self.openephys_url = openephys_url

        socket = self.make_socket()
        socket.send(b'config')
        msg = socket.recv()
        self.stream_params = json.loads(msg.decode())
        socket.close()
        # ~ pprint(self.stream_params)

    def make_socket(self):
        context = zmq.Context.instance()
        socket = context.socket(zmq.REQ)
        socket.linger = 1000  # don't let socket deadlock when exiting
        socket.connect(self.openephys_url)
        return socket

    def _initialize(self):
        pass

    def after_output_configure(self, outputname):
        # here a hack to get the buffer before start/stop
        stream = InputStream()
        stream.connect(self.stream_params)
        stream.set_buffer(size=self.stream_params['buffer_size'])
        self._start()
        pos, data = stream.recv(return_data=True)
        self._stop()
        n_ampl = data.shape[0]

        _, n_chan = self.stream_params['shape']
        self.stream_params['shape'] = (n_ampl, n_chan)

        if outputname == 'signals':
            self.outputs['signals'].params.update(self.stream_params)

    def _start(self):
        socket = self.make_socket()
        socket.send(b'start')
        msg = socket.recv()
        assert msg == b'ok'
        socket.close()

    def _stop(self):
        socket = self.make_socket()
        socket.send(b'stop')
        msg = socket.recv()
        assert msg == b'ok'

    def _close(self):
        pass


register_node_type(OpenEphysGUIRelay)
