# -*- coding: utf-8 -*-
# Copyright (c) 2016, French National Center for Scientific Research (CNRS)
# Distributed under the (new) BSD License. See LICENSE for more info.

from .arraytools import make_dtype
from pyacq.core.rpc.proxy import ObjectProxy

all_transfermodes = {}

def register_transfermode(modename, sender, receiver):
    global all_transfermodes
    all_transfermodes[modename] = (sender, receiver)


class DataSender:
    """Base class for OutputStream data senders.

    Subclasses are used to implement different methods of data transmission.
    """
    def __init__(self, socket, params):
        self.socket = socket
        self.params = params
        #~ if isinstance(self.params, ObjectProxy):
            #~ self.params = self.params._get_value()
        #~ if 'dtype' in self.params:
            #~ self.params['dtype'] = make_dtype(self.params['dtype'])
        self.funcs = []

    def send(self, index, data):
        raise NotImplementedError()
    
    def close(self):
        pass

    def reset_index(self):
        pass


class DataReceiver:
    """Base class for InputStream data receivers.

    Subclasses are used to implement different methods of data transmission.
    """
    def __init__(self, socket, params):
        self.socket = socket
        self.params = params
        #~ if isinstance(self.params, ObjectProxy):
            #~ self.params = self.params._get_value()
        #~ if 'dtype' in self.params:
            #~ self.params['dtype'] = make_dtype(self.params['dtype'])
        self.buffer = None
            
    def recv(self, return_data=False):
        raise NotImplementedError()
    
    def close(self):
        pass
