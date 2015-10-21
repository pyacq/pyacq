# -*- coding: utf-8 -*-
"""
Example for recording the three emotiv streams.
"""
from pyacq import StreamHandler, EmotivMultiSignals, RawDataRecording
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

def record_emotiv():
    streamhandler = StreamHandler()

    # Configure and start
    dev = EmotivMultiSignals(streamhandler = streamhandler)
    dev.configure(buffer_length = 1800)
    dev.initialize()
    #dev.start()

    dirname_base = os.path.join(user.home, 'Projets/pyacq_emotiv_recording')
    print dirname_base
    if not os.path.exists(dirname_base):
        os.mkdir(dirname_base)
    dirname = os.path.join(dirname_base, 'rec {}'.format(datetime.datetime.now()))
    if not os.path.exists(dirname):
        os.mkdir(dirname)

    streams = [dev.streams[0], dev.streams[1], dev.streams[2]]
    rec = RawDataRecording(streams, dirname)
    rec.start()
    dev.start()

    time.sleep(300.)

    rec.stop()
    dev.stop()
    dev.close()


if __name__ == '__main__':
    record_emotiv()
