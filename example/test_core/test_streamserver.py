# -*- coding: utf-8 -*-
"""
This test the stream server concept (distant streamhandler)
"""

from pyacq import StreamHandler, StreamServer, StreamHandlerProxy
from pyacq import FakeMultiSignals

import time
import numpy as np




def test1():
    streamserver = StreamServer()
    dev = FakeMultiSignals(streamhandler = streamserver)
    dev.configure()
    dev.initialize()
    dev.start()
    
    print streamserver.get_stream_list()
    
    time.sleep(1.)
    
    streamhandlerproxy = StreamHandlerProxy()
    print streamhandlerproxy.get_stream_list()
    
    
    dev.stop()
    dev.close()
    streamserver.stop()
    



if __name__ == '__main__':
    test1()
