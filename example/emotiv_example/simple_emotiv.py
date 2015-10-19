# -*- coding: utf-8 -*-
"""



"""

from pyacq import StreamHandler, EmotivMultiSignals

import zmq
import msgpack
import time
import multiprocessing as mp


def test_recv_loop(port, stop_recv):
    print 'start receiver loop', port
    context = zmq.Context()
    socket = context.socket(zmq.SUB)
    socket.setsockopt(zmq.SUBSCRIBE, '')
    socket.connect("tcp://localhost:{}".format(port))
    while stop_recv.value == 0:
        message = socket.recv()
        pos = msgpack.loads(message)
        print 'On port {} read pos is {}'.format(port, pos)
    print 'stop receiver'


def run_Emotiv():
    streamhandler = StreamHandler()

    # Configure and start
    dev = EmotivMultiSignals(streamhandler=streamhandler)
    dev.configure(buffer_length=1800)
    dev.initialize()
    dev.start()

    # Create and starts receiver with multuprocessing
    stream_chan = dev.streams[0]
    stream_imp = dev.streams[1]
    stream_gyro = dev.streams[2]
    stop_recv = mp.Value('i', 0)
    process_chan = mp.Process(
        target=test_recv_loop, args=(stream_chan['port'], stop_recv))
    process_imp = mp.Process(
        target=test_recv_loop, args=(stream_imp['port'], stop_recv))
    process_gyro = mp.Process(
        target=test_recv_loop, args=(stream_gyro['port'], stop_recv))

    process_chan.start()
    process_imp.start()
    process_gyro.start()

    time.sleep(10.)
    stop_recv.value = 1

    process_chan.join()
    process_imp.join()
    process_gyro.join()

    # Stope and release the device
    dev.stop()
    dev.close()


if __name__ == '__main__':
    run_Emotiv()
