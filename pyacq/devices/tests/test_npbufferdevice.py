import time

from pyacq.core.nodegroup import NodeGroup
from pyacq.core.processspawner import ProcessSpawner
from pyacq.core.rpc import RPCClient, RemoteCallException
from pyacq.core.node import Node
from pyacq.core.stream import StreamSender, StreamReceiver
from pyacq.devices.npbufferdevice import NumpyDeviceBuffer


def test_npbufferdevice():
    name, addr = 'nodegroup', 'tcp://127.0.0.1:6000'
    process_nodegroup0  = ProcessSpawner(NodeGroup,  name, addr)
    client0 = RPCClient(name, addr)
    
    # create and configure device
    client0.create_node('dev', 'NumpyDeviceBuffer')
    client0.control_node('dev', 'configure', nb_channel = 16, sample_interval = 0.001)
    stream_dict = dict(protocol = 'tcp', interface = '127.0.0.1', port = '9000',
                        transfertmode = 'plaindata', streamtype = 'analogsignal',
                        dtype = 'float32', shape = (-1, 16), compression ='',
                        scale = None, offset = None, units = '' )
    client0.control_node('dev', 'create_outputs', [ stream_dict ])
    client0.control_node('dev', 'initialize')
    
    # create some receveiver
    receiver_names = [ 'receiver{}'.format(i) for i in range(3) ]
    
    # create stream
    for name in receiver_names:
        client0.create_node(name, '_MyReceiverNode')
        client0.control_node(name, 'configure')
        client0.control_node(name, 'set_inputs', [ stream_dict ])
        client0.control_node(name, 'initialize')
    
    time.sleep(1.)
    client0.start_all()
    print(client0.any_node_running())
    time.sleep(3.)
    
    client0.stop_all()
    print(client0.any_node_running())
    process_nodegroup0.stop()
    



    
    
if __name__ == '__main__':
    test_npbufferdevice()

 
