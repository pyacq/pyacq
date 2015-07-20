#~ import time
#~ import pytest
#~ import logging

from pyacq.core.rpc import RPCClient, RemoteCallException
from pyacq.core.processspawner import ProcessSpawner
from pyacq.core.nodegroup import NodeGroup
from pyacq.core.node import Node



def test_stream():
    name, addr = 'nodegroup', 'tcp://127.0.0.1:6000'
    process_nodegroup0  = ProcessSpawner(NodeGroup,  name, addr)
    client0 = RPCClient(name, addr)
    
    client0.create_node('mynode0', '_MyTestNode')
    client0.create_node('mynode1', '_MyTestNode')
    
    protocol = tcp/udp/inproc/ipc
    addr
    port
    
    transfertmode = plaindata/sharedmeme/(sharecuda/sharecl)
    streamtype = analogsignal/digitalsignal/event/image/video
    dtype =  float64/float32/int32
    nb channel/shape
    shape
    compression None/blosc(blosc-lz4-snappy-../)/codec_avi
    axislabel = 
    scale
    offset
    units
    
    
    
    stream =Stream(
    
    some_stream_dict = stream.to_json()
    
    some_stream_dict = {'addr' : 'localhost' }
    
    client0.control_node('mynode0', 'set_source', args = some_stream_dict)
    
    
    
    
    mystreamout.new_frame(lkjlskdjfsdf)
    
    
    mystreamin.get_last_frame()
    mystreamin.get_a_slice()
    
    
    
    



if __name__ == '__main__':
    test_stream()
