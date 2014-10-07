# -*- coding: utf-8 -*-
"""
"""

from pyacq import StreamHandler, FakeMultiSignals, FakeMultiSignalsAndTriggers
from pyacq.gui import Oscilloscope
import multiprocessing as mp

import msgpack
#~ import gevent
#~ import zmq.green as zmq

from PyQt4 import QtCore,QtGui

import zmq
import msgpack
import time
import numpy as np

def test1():
    streamhandler = StreamHandler()
    
    filename = 'cerveau_alex.raw'
    precomputed = np.fromfile(filename , dtype = np.float32).reshape(-1, 14).transpose()

    # Configure and start
    dev = FakeMultiSignals(streamhandler = streamhandler)
    dev.configure( #name = 'Test dev',
                                nb_channel = 14,
                                sampling_rate =128.,
                                buffer_length = 30.,
                                packet_size = 1,
                                precomputed = precomputed,
                                )
    dev.initialize()
    dev.start()
    
    app = QtGui.QApplication([])
    
    w1=Oscilloscope(stream = dev.streams[0])
    w1.show()
    w1.auto_gain_and_offset(mode = 1)
    w1.set_params(xsize = 10.)

    
    app.exec_()
    
    # Stope and release the device
    dev.stop()
    dev.close()
# example de replay avec trigger a partir d'un fichier brainvision (et neo)





def test_recv_loop(stream, stop_recv):
    context = zmq.Context()
    socket = context.socket(zmq.SUB)
    socket.setsockopt(zmq.SUBSCRIBE,'')
    socket.connect("tcp://localhost:{}".format(stream['port']))
    while stop_recv.value==0:
        message = socket.recv()
        trigger = np.frombuffer(message, dtype = stream['dtype'])
        print trigger
    print 'stop receiver'



class ThreadListenTriggers(QtCore.QThread):
    new_trig = QtCore.pyqtSignal(int, str)
    def __init__(self, parent=None, stream = None):
        QtCore.QThread.__init__(self, parent)
        self.running = False
        
        self.stream = stream
        
    
    def run(self):
        context = zmq.Context()
        socket = context.socket(zmq.SUB)
        socket.setsockopt(zmq.SUBSCRIBE,'')
        socket.connect("tcp://localhost:{}".format(self.stream['port']))
        
        
        self.running = True
        while self.running:
            events = socket.poll(50)
            if events ==0:
                time.sleep(.05)
                continue
            message = socket.recv()
            trigger = np.frombuffer(message, dtype = self.stream['dtype'])
            self.new_trig.emit(int(trigger['pos']), str(trigger['label']))
    
    def stop(self):
        self.running = False



def test2():
    import neo
    
    bl = neo.BrainVisionIO(filename = 'KLAJU_0002.vhdr').read()[0]
    seg = bl.segments[0]
    precomputed_sigs = np.concatenate( [[sig.magnitude] for sig in seg.analogsignals] )
    sr = bl.segments[0].analogsignals[0].sampling_rate.rescale('Hz').magnitude
    nb_channel = precomputed_sigs.shape[0]
    
    #~ print [ e.times.size for e in seg.eventarrays ] 
    # IL y a deux eventarray dans le fichie ron prend le 2eme
    trig_times = seg.eventarrays[1].times.rescale('s').magnitude
    trig_pos = (trig_times*sr).astype('int64')
    trig_labels = seg.eventarrays[1].labels
    
    # on rabotte pour eviter d'attendre
    pos0 = trig_pos[0]-1
    trig_pos -= pos0
    precomputed_sigs = precomputed_sigs[:, pos0:]
    
    #~ print trig_times[:20]
    #~ print trig_labels[:20]
    precomputed_trigs = np.array( zip(trig_pos,trig_labels) , dtype = [('pos', 'int64'), ('label', 'S4'), ])
    
    
    
    
    print precomputed_trigs[:20]

    
    print 'sampling rate', sr
    print 'nb_channel rate', nb_channel
    print 'nb triggers', precomputed_trigs.size
    
    streamhandler = StreamHandler()
    
    # Configure and start
    dev = FakeMultiSignalsAndTriggers(streamhandler = streamhandler)
    dev.configure( #name = 'Test dev',
                                nb_channel = nb_channel,
                                sampling_rate =sr,
                                buffer_length = 30.,
                                packet_size = 20,
                                precomputed_sigs = precomputed_sigs,
                                precomputed_trigs = precomputed_trigs,
                                )
    dev.initialize()
    dev.start()
    
    def on_new_trigger(pos, label):
        print pos, label
        print type(pos), type(label)
        
    
    app = QtGui.QApplication([])
    
    w1=Oscilloscope(stream = dev.streams[0])
    w1.show()
    w1.auto_gain_and_offset(mode = 1)
    w1.set_params(xsize = 10.)
    
    listen_trigger = ThreadListenTriggers(stream = dev.streams[1])
    listen_trigger.new_trig.connect(on_new_trigger)
    listen_trigger.start()
    
    app.exec_()
    
    # Stope and release the device
    dev.stop()
    dev.close()
    process.stop()



if __name__ == '__main__':
    #~ test1()
    test2()
