# -*- coding: utf-8 -*-

 
 
class DeviceBase:
    def __init__(self, streamhandler = None):
        self.running = False
        self.configured = False
        self.streamhandler = streamhandler
    
    #~ def configure(self, **kargs):
        #~ self.params = { }
        #~ self.params.update(kargs)
        #~ self.__dict__.update(kargs)
        #~ self.configured = True

    def initialize(self):
        raise NotImplementedError

    def start(self):
        raise NotImplementedError

    def stop(self):
        raise NotImplementedError

    def close(self):
        raise NotImplementedError


