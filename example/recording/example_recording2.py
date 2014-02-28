# -*- coding: utf-8 -*-
"""
Example for recording 2 streams.
"""

from pyacq import StreamHandler, FakeMultiSignals, FakeDigital, RawDataRecording
from pyacq.processing.trigger import AnalogTrigger
import msgpack


import zmq
import time

import os
import user
import datetime

import numpy as np

import neo
import quantities as pq
#~ import OpenElectrophy
from OpenElectrophy.gui.viewers import SignalViewer, SegmentViewer
from PyQt4 import QtCore,QtGui



def test2():
    # record on trigger
    
    streamhandler = StreamHandler()
    
    
    dev0 = FakeMultiSignals(streamhandler = streamhandler)
    dev0.configure(
                                nb_channel = 16,
                                sampling_rate =1000.,
                                buffer_length = 64,
                                packet_size = 10,
                                last_channel_is_trig = True,
                                )
    
    dev1 = FakeDigital(streamhandler = streamhandler)
    dev1.configure(
                                nb_channel = 10,
                                sampling_rate =1000.,
                                buffer_length = 10.,
                                packet_size = 128,
                                )
    
    devs = [dev0, dev1]
    #~ devs = [dev0]
    
    for dev in devs:
        dev.initialize()

    dirname_base = os.path.join(user.home, 'test_pyacq_recording')
    if not os.path.exists(dirname_base):
        os.mkdir(dirname_base)
    dirname = os.path.join(dirname_base, 'rec {}'.format(datetime.datetime.now()))
    if not os.path.exists(dirname):
        os.mkdir(dirname)
        
    
    global is_started
    is_started = 0
    
    def start_rec(pos):
        global is_started
        is_started +=1
        if is_started!=5:
            return
        print 'start_rec', pos, is_started
        streams = [dev.streams[0] for dev in  devs]
        
        bound_indexes = {dev0.streams[0] : (pos-1000, pos+1000),
                                            dev1.streams[0] : (pos-1000, pos+1000),
                         }
        rec = RawDataRecording(streams, dirname, bound_indexes = bound_indexes)
        rec.start()
        

    #~ trigger.start()
    
    
    for dev in devs:
        dev.start()
    
    trigger = AnalogTrigger(stream = dev0.streams[0],
                                    threshold = 0.25,
                                    front = '+', 
                                    channel = dev0.nb_channel-1,
                                    #~ debounce_mode = 'no-debounce',
                                    #~ debounce_mode = 'after-stable',
                                    debounce_mode = 'before-stable',
                                    debounce_time = 0.05,
                                    callbacks = [ start_rec,  ]
                                    )    
    time.sleep(5.)
    
    #~ rec.stop()
    
    # Stope and release the device
    for dev in devs:
        dev.stop()
        dev.close()
    
    
    # Read the files
    reader = neo.RawBinarySignalIO(filename = os.path.join(dirname, 'fake 16 analog input.raw'))
    seg = reader.read_segment(sampling_rate = 1.*pq.kHz,
                                            t_start = 0.*pq.s,
                                            unit = pq.V,
                                            nbchannel = 16,
                                            dtype = np.float32,
                                            )
    app = QtGui.QApplication([])
    viewer = SegmentViewer(segment = seg)
    #~ viewer = SignalViewer(analogsignals = seg.analogsignals, with_time_seeker = True)
    viewer.show()
    
    print seg.analogsignals[0].shape
    sig = seg.analogsignals[-1].magnitude
    print np.where((sig[:-1]<.25)&(sig[1:]>=.25))
    
    analogsignals2 = [ ]
    arr = np.memmap(filename = os.path.join(dirname, u'fake 10 digital input.raw'), mode = 'r', dtype = np.uint8)
    arr = arr.reshape(-1, 2)
    print arr.shape
    for chan in range(10):
        b = chan//8
        mask = 1<<(chan%8)
        sig = (arr[:,b]&mask>0).astype(float)
        analogsignals2.append(neo.AnalogSignal(sig*pq.V, t_start = 0*pq.s, sampling_rate = 1*pq.kHz))
    viewer2 = SignalViewer(analogsignals = analogsignals2, with_time_seeker = True)
    
    viewer2.show()
    
    
    app.exec_()    


if __name__ == '__main__':
    test2()


