from pyacq.core.stream  import OutputStream, InputStream
from pyacq.core.tools  import ThreadPollInput
from pyqtgraph.Qt import QtCore, QtGui
import pyqtgraph as pg

import numpy as np
import weakref
import time


def test_ThreadPollInput():
    app = pg.mkQApp()
    
    nb_channel = 16
    chunksize = 1024
    stream_spec = dict(protocol = 'tcp', interface = '127.0.0.1', port='*', 
                       transfermode = 'plaindata', streamtype = 'analogsignal',
                       dtype = 'float32', shape = (-1, nb_channel), compression ='',
                       scale = None, offset = None, units = '')
    
    class ThreadSender(QtCore.QThread):
        def __init__(self, output_stream, parent = None):
            QtCore.QThread.__init__(self, parent)
            self.output_stream = weakref.ref(output_stream)
        
        def run(self):
            index = 0
            for i in range(5):
                index += chunksize
                arr = np.random.rand(chunksize, nb_channel).astype(stream_spec['dtype'])
                self.output_stream().send(index, arr)
                time.sleep(0.05)
            self.terminated.emit()
    
    
    outstream = OutputStream()
    outstream.configure(**stream_spec)
    instream = InputStream()
    instream.connect(outstream)
    
    sender = ThreadSender(output_stream = outstream)
    poller = ThreadPollInput(input_stream = instream)
    
    def on_new_data(pos, arr):
        print(pos, arr.shape)
    
    def terminate():
        sender.wait()
        poller.stop()
        poller.wait()
        app.quit()
    
    sender.terminated.connect(terminate)
    poller.new_data.connect(on_new_data)
    
    poller.start()
    sender.start()
    
    app.exec_()

    

if __name__ == '__main__':
    test_ThreadPollInput()