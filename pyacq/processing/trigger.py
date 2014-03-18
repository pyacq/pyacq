# -*- coding: utf-8 -*-
"""

"""

import multiprocessing as mp
import numpy as np
import msgpack

import threading

import zmq





# debounce_time
# debounce_mode = after_stable    before_stable

"""
CTR_TRIGGER_AFTER_STABLE: This mode rejects glitches and only passes state transitions after a specified period of stability
(the debounce time). This mode is used with electromechanical devices like encoders and mechanical switches to reject switch
bounce and disturbances due to a vibrating encoder that is not otherwise moving. The debounce time should be set short
enough to accept the desired input pulse but longer than the period of the undesired disturbance.
CTR_TRIGGER_BEFORE_STABLE: Use this mode when the input signal has groups of glitches and each group is to be counted
as one. The trigger before stable mode will recognize and count the first glitch within a group but reject the subsequent glitches
within the group if the debounce time is set accordingly. In this case the debounce time should be set to encompass one entire
group of glitches
"""







class TriggerBase:
    def __init__(self, stream, channel = 0, threshold = 1., front = '+',
                            debounce_mode = 'no-debounce', # 'after-stable' , 'before-stable'
                            debounce_time = 0.01,
                            callbacks = [ ],
                            autostart = True,
                            ):    
        self.stream = stream
        self.context = zmq.Context()
        
        
        self.channel = channel
        self.threshold =threshold
        self.front = front
        self.debounce_mode = debounce_mode
        self.debounce_time = debounce_time
        self.callbacks = callbacks
        
        self.np_array = self.stream['shared_array'].to_numpy_array()
        self.half_size = self.np_array.shape[1]/2
        
        if autostart:
            self.start()
    
    def start(self):
        self.running = True
        self.thread = threading.Thread(target = self.loop)
        self.thread.start()
    
    def stop(self):
        self.running =False
        self.thread.join()
    
    def set_params(self, **kargs):
        for k, v in kargs.items():
            assert k in ['channel', 'threshold', 'front',
                        'debounce_mode', 'debounce_time']
            setattr(self, k, v)
            
    def loop(self):
        port = self.stream['port']
        socket = self.context.socket(zmq.SUB)
        socket.setsockopt(zmq.SUBSCRIBE,'')
        socket.connect("tcp://localhost:{}".format(port))
        #~ self.last_pos = 0
        message = socket.recv()
        self.last_pos = msgpack.loads(message)
        while self.running:
            message = socket.recv()
            pos = msgpack.loads(message)
            
            db = int(self.debounce_time*self.stream['sampling_rate'])
            
            if self.debounce_mode == 'no-debounce':
                pass
            elif self.debounce_mode == 'after-stable':
                pos -= db
            elif self.debounce_mode == 'before-stable':
                pos -= db*2
            new = pos - self.last_pos
            if new<2: continue
            head = pos%self.half_size+self.half_size
            tail = head - new
            
            newbuf = self.get_buffer_from_channel(tail, head)
            sig1 = newbuf[:-1]
            sig2 = newbuf[1:]
            
            if self.front == '+':
                crossings,  = np.where( (sig1 <= self.threshold) & ( sig2>self.threshold) )
            elif self.front == '-':
                crossings,  = np.where( (sig1 >= self.threshold) & ( sig2<self.threshold) )
            crossings +=1
            
            if self.debounce_mode == 'no-debounce':
                pass
            elif self.debounce_mode == 'after-stable':
                if self.front == '+':
                    for i, crossing in enumerate(crossings):
                        if np.any(newbuf[crossing:crossing+db]<self.threshold):
                            crossings[i] = -1
                elif self.front == '-':
                    for i, crossing in enumerate(crossings):
                        if np.any(newbuf[crossing:crossing+db]>self.threshold):
                            crossings[i] = -1
                crossings = crossings[crossings != -1]
            elif self.debounce_mode == 'before-stable':
                if self.front == '+':
                    for i, crossing in enumerate(crossings):
                        if crossing == -1: continue
                        if np.any(newbuf[crossing+db:crossing+db*2]<self.threshold):
                            crossings[i] = -1
                        else:
                            crossings[i+1:][(crossings[i+1:]-crossing)<db] = -1
                elif self.front == '-':
                    for i, crossing in enumerate(crossings):
                        if crossing == -1: continue
                        if np.any(newbuf[crossing+db:crossing+db*2]>self.threshold):
                            crossings[i] = -1
                        else:
                            crossings[i+1:][(crossings[i+1:]-crossing)<db] = -1
                crossings = crossings[crossings != -1]
            
            for crossing in crossings:
                for callback in self.callbacks:
                    callback(crossing+self.last_pos)
                
            
            self.last_pos = pos-1
            


class AnalogTrigger(TriggerBase):
    def __init__(self, **kargs):
        TriggerBase.__init__(self, **kargs)
        assert type(self.stream).__name__ == 'AnalogSignalSharedMemStream'

    def get_buffer_from_channel(self, tail, head):
        return self.np_array[self.channel, tail:head]


class DigitalTrigger(TriggerBase):
    def __init__(self, **kargs):
        kargs['threshold'] = .5
        TriggerBase.__init__(self, **kargs)
        assert type(self.stream).__name__ == 'DigitalSignalSharedMemStream'
        
        self.b = self.channel//8
        self.mask = 1<<(self.channel%8)

    def get_buffer_from_channel(self, tail, head):
        return self.np_array[self.b, tail:head]&self.mask


