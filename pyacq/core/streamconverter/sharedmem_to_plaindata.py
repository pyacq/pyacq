# -*- coding: utf-8 -*-
"""


"""


import numpy as np
import zmq
import threading

import blosc
import msgpack
import time

class AnaSigSharedMem_to_AnaSigPlainData:
    """
    This class take a AnalogSignalSharedMemStream and generate a AnalogSignalPlainDataStream.
    
    
    
    
    """
    def __init__(self, streamhandler,  sharedmem_stream, plaindata_port = None,
                                        info_port = None, autostart = True, compress = 'blosc',
                                        channel_mask = None):
        s1 = self.sharedmem_stream = sharedmem_stream
        self.streamhandler = streamhandler
        self.channel_mask = channel_mask
        if self.channel_mask is None:
            self.channel_mask = np.ones(sharedmem_stream['nb_channel'], dtype = bool)
        self.compress = compress
        
        self.plaindata_stream = self.streamhandler.new_AnalogSignalPlainDataStream(
                                                name = s1['name']+'converted',
                                                sampling_rate = s1['sampling_rate'],
                                                nb_channel = int(np.sum(self.channel_mask)),
                                                packet_size = s1['packet_size'],
                                                dtype = s1['shared_array'].dtype,
                                                channel_indexes =  [  n  for n,m in zip(s1['channel_indexes'],self.channel_mask) if m],
                                                channel_names = [  n for n,m in zip(s1['channel_names'],self.channel_mask) if m ],
                                                port = plaindata_port,
                                                compress = compress,
                                                )
        
        self.context = zmq.Context()
        self.recv_socket = self.context.socket(zmq.SUB)
        self.recv_socket.setsockopt(zmq.SUBSCRIBE,'')
        self.recv_socket.connect("tcp://localhost:{}".format(self.sharedmem_stream['port']))

        self.send_socket = self.context.socket(zmq.PUB)
        self.send_socket.bind("tcp://*:{}".format(self.plaindata_stream['port']))

        self.info_socket = self.context.socket(zmq.REP)
        self.info_socket.bind("tcp://*:{}".format(info_port))

        
        self.running = True
        
        if autostart:
            self.start()
    
    
    def start(self):
        self.thread_recv = threading.Thread(target = self.recv_loop)
        
        
        self.thread_info = threading.Thread(target = self.info_loop)
        
        self.thread_info.start()
        self.thread_recv.start()
        
    def stop(self):
        self.running = False
        #~ self.recv_socket.close()
        self.thread_recv.join()
        #~ self.info_socket.close()
        self.thread_info.join()
        
    
    
    
    def recv_loop(self):
        last_pos = None
        np_array = self.sharedmem_stream['shared_array'].to_numpy_array()        
        half_size = np_array.shape[1]/2
        while self.running:
            message = self.recv_socket.recv()
            abs_pos = msgpack.loads(message)
            if last_pos == None:
                last_pos = abs_pos
                continue
            new = (abs_pos-last_pos)
            if new>half_size: new = half_size
            head = abs_pos%half_size+half_size
            tail = head - new
            chunk = np_array[self.channel_mask, tail:head].transpose()
            
            
            
            if self.compress is None:
                buf = chunk
            elif self.compress is 'blosc':
                buf = blosc.compress(chunk.tostring(), typesize = chunk.dtype.itemsize, clevel= 9)
            #~ print 'sended', abs_pos, len(chunk.tostring()), len(chunk.tostring()), chunk.shape
            self.send_socket.send_multipart([msgpack.dumps(abs_pos), buf ])#, flags = zmq.NOBLOCK)
            last_pos = abs_pos



    def info_loop(self):
        while self.running:
            #~ try:
                #~ message = self.info_socket.recv(flags = zmq.NOBLOCK)
            #~ except:
         #~ #   except zmq.EAGAIN:
                #~ time.sleep(.1)
                #~ continue
            events =  self.info_socket.poll(50)
            if events ==0:
                time.sleep(.1)
                continue
            
            message = self.info_socket.recv()
            
            if message == 'info_json':
                info = dict(self.plaindata_stream._params)
                info['dtype'] = str(info['dtype'])
                self.info_socket.send_json(info)
            else:
                self.info_socket.send('')



