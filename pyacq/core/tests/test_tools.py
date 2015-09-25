from pyacq.core.stream  import OutputStream, InputStream
from pyacq.core.tools  import ThreadPollInput, StreamConverter, StreamSplitter
from pyqtgraph.Qt import QtCore, QtGui
import pyqtgraph as pg

import numpy as np
import weakref
import time

nb_channel = 16
chunksize = 1024

stream_spec = dict(protocol = 'tcp', interface = '127.0.0.1', port='*', 
                   transfermode = 'plaindata', streamtype = 'analogsignal',
                   dtype = 'float32', shape = (-1, nb_channel), timeaxis = 0, 
                   compression ='', scale = None, offset = None, units = '')


class ThreadSender(QtCore.QThread):
    def __init__(self, output_stream, parent = None):
        QtCore.QThread.__init__(self, parent)
        self.output_stream = weakref.ref(output_stream)
    
    def run(self):
        index = 0
        for i in range(10):
            index += chunksize
            arr = np.random.rand(chunksize, nb_channel).astype(stream_spec['dtype'])
            self.output_stream().send(index, arr)
            time.sleep(0.05)
        self.terminated.emit()


def test_ThreadPollInput():
    app = pg.mkQApp()
    
    outstream = OutputStream()
    outstream.configure(**stream_spec)
    instream = InputStream()
    instream.connect(outstream)
    
    sender = ThreadSender(output_stream = outstream)
    poller = ThreadPollInput(input_stream = instream)
    
    
    global last_pos
    last_pos= 0
    def on_new_data(pos, arr):
        assert arr.shape==(chunksize, nb_channel)
        global last_pos
        last_pos += chunksize
        assert last_pos==pos
    
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


def test_streamconverter():
    app = pg.mkQApp()
    
    nb_channel = 16
    chunksize = 1024
    stream_spec = dict(protocol = 'tcp', interface = '127.0.0.1', port='*', 
                       transfermode = 'plaindata', streamtype = 'analogsignal',
                       dtype = 'float32', shape = (-1, nb_channel), timeaxis = 0, 
                       compression ='', scale = None, offset = None, units = '')
    
    outstream = OutputStream()
    outstream.configure(**stream_spec)
    sender = ThreadSender(output_stream = outstream)
    
    stream_spec2 = dict(protocol = 'tcp', interface = '127.0.0.1', port='*', 
                   transfermode = 'sharedarray', streamtype = 'analogsignal',
                   dtype = 'float32', shape = (nb_channel, -1), timeaxis = 1, 
                   compression ='', scale = None, offset = None, units = '',
                   sharedarray_shape = ( nb_channel, chunksize*20), ring_buffer_method = 'double',
                   )

    
    
    conv = StreamConverter()
    conv.configure()
    conv.input.connect(outstream)
    conv.output.configure(**stream_spec2)
    conv.initialize()

    instream = InputStream()
    instream.connect(conv.output)

    global last_pos
    last_pos= 0
    def on_new_data(pos, arr):
        assert arr is None
        global last_pos
        last_pos += chunksize
        assert last_pos==pos
    
    def terminate():
        sender.wait()
        conv.stop()        
        poller.stop()
        poller.wait()
        app.quit()

    poller = ThreadPollInput(input_stream = instream)
    sender.terminated.connect(terminate)
    poller.new_data.connect(on_new_data)
    
    
    poller.start()
    conv.start()
    sender.start()
    
    
    app.exec_()

def test_stream_splitter():
    app = pg.mkQApp()
    
    nb_channel = 16
    chunksize = 1024
    stream_spec = dict(protocol = 'tcp', interface = '127.0.0.1', port='*', 
                       transfermode = 'plaindata', streamtype = 'analogsignal',
                       dtype = 'float32', shape = (-1, nb_channel), timeaxis = 0, 
                       compression ='', scale = None, offset = None, units = '')
    
    outstream = OutputStream()
    outstream.configure(**stream_spec)
    sender = ThreadSender(output_stream = outstream)

    def on_new_data(pos, arr):
        assert arr.shape==(1024,1)
        #print(pos, arr.shape)
    
    all_instream = []
    all_poller = []
    splitter = StreamSplitter()
    splitter.configure(nb_channel = nb_channel)
    splitter.input.connect(outstream)
    for name, output in splitter.outputs.items():
        output.configure(shape = (-1, 1))
        instream = InputStream()
        instream.connect(output)
        poller = ThreadPollInput(input_stream = instream)
        poller.new_data.connect(on_new_data)
        all_instream.append(instream)
        all_poller.append(poller)
    splitter.initialize()

    def terminate():
        sender.wait()
        splitter.stop()
        for poller in all_poller:
            poller.stop()
            poller.wait()
        app.quit()

    sender.terminated.connect(terminate)
    
    for poller in all_poller:
        poller.start()
    
    splitter.start()
    sender.start()
    
    
    app.exec_()
    
    

if __name__ == '__main__':
    test_ThreadPollInput()
    test_streamconverter()
    test_stream_splitter()
