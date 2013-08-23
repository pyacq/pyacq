# -*- coding: utf-8 -*-
"""


"""


import numpy as np
import zmq
import threading

import blosc
import msgpack

import time

class AnaSigPlainData_to_AnaSigSharedMem:
    """
    This class take a AnalogSignalPlainDataStream  and generate a AnalogSignalSharedMemStream.
    
    The mechanism is this one:
       * listen with zmq.REG the info adress of the stream
       * get info dict on that stream
       * start a socket on new givien the info['port']
       * loop for get chink of data
       * if a timeout is too big between data restart the stream
    
    
    
    """
    def __init__(self, streamhandler,  plaindata_info_addr, buffer_length = 10.,
                                        autostart = True, timeout_reconnect = .5):
        
        self.plaindata_info_addr = plaindata_info_addr
        self.streamhandler = streamhandler
        self.buffer_length = buffer_length
        self.timeout_reconnect = timeout_reconnect
        
        self.running = True
        self.sharedmem_stream = None
        if autostart:
            self.start(first_start = True)
    
    
    def start(self, first_start = True):
        context = zmq.Context()
        
        
        ## get info on info socket
        info_socket = context.socket(zmq.REQ)
        
        info_socket.connect(self.plaindata_info_addr)
        info_socket.send('info_json')
        info = info_socket.recv_json()
        
        # create stream socket : send and recv
        
        kargs = dict(info)
        self.compress = kargs.pop('compress')
        kargs['buffer_length'] = self.buffer_length
        kargs['port'] = None
        if first_start:
            # first start
            self.sharedmem_stream = self.streamhandler.new_AnalogSignalSharedMemStream(**kargs)
            self.send_socket = context.socket(zmq.PUB)
            self.send_socket.bind("tcp://*:{}".format(self.sharedmem_stream['port']))
        else:
            #restart
            assert self.sharedmem_stream['nb_channel'] == info['nb_channel'], 'recv stream have change nb_channel'
        
        self.recv_socket = context.socket(zmq.SUB)
        self.recv_socket.setsockopt(zmq.SUBSCRIBE,'')
        addr = self.plaindata_info_addr
        while not addr.endswith(':'):
            addr = addr[:-1]
        addr += str(info['port'])
        self.recv_socket.connect(addr)
        
        self.last_packet_time = time.time()
        self.last_pos = 0
        
        if first_start:
            self.thread_recv = threading.Thread(target = self.recv_loop)
            self.thread_recv.start()
        


    def stop(self):
        self.running = False
        self.thread_recv.join()
    
    
    
    def recv_loop(self):
        
        np_array = self.sharedmem_stream['shared_array'].to_numpy_array()        
        half_size = np_array.shape[1]/2
        n = self.sharedmem_stream['nb_channel']
        while self.running:
            events = self.recv_socket.poll(50)
            if events ==0:
                time.sleep(.05)
                if time.time()- self.last_packet_time>self.timeout_reconnect:
                    np_array[:]=0
                    self.start(first_start = False)
                continue
            m0,m1 = self.recv_socket.recv_multipart()
            self.last_packet_time = time.time()
            
            abs_pos = msgpack.loads(m0)
            if self.last_pos>abs_pos:
                print 'restart because last not googd'
                self.start(first_start = False)
                
                continue
            
            if self.compress is None:
                buf = buffer(m1)
            elif self.compress == 'blosc':
                buf = blosc.decompress(m1)
            
            chunk = np.frombuffer(buf, dtype = np_array.dtype, ).reshape(-1, n).transpose()
            #~ print 'recv', abs_pos, chunk.shape
            
            new = chunk.shape[1]
            head = abs_pos%half_size+half_size
            tail = head - new
            np_array[:,  tail:head] = chunk

            head = abs_pos%half_size+half_size
            tail = head - new
            np_array[:,  tail:head] = chunk
            head2 = abs_pos%half_size
            tail2 = max(head2 - new, 0)
            new2 = head2-tail2
            if new2!=0:
                np_array[:,  tail2:head2] = chunk[:, -new2:]

            self.send_socket.send(msgpack.dumps(abs_pos))
            self.last_pos = abs_pos
            
            
            

    
    def info_loop(self):
        pass
        #self.channel_mask
