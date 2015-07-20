import time
import pytest

from pyacq.core.rpc import RPCClient, RemoteCallException
from pyacq.core.processspawner import ProcessSpawner
from pyacq.core.nodegroup import NodeGroup
from pyacq.core.node import Node

def test_nodegroup0():
    
    name, addr = 'nodegroup', 'tcp://127.0.0.1:6000'
    process_nodegroup0  = ProcessSpawner(NodeGroup,  name, addr)
    client0 = RPCClient(name, addr)
    
    n = 5
    
    for i in range(n):
        client0.create_node('mynode{}'.format(i), '_MyTestNode').result()

    for i in range(n):
        client0.control_node('mynode{}'.format(i), 'start').result()
    #time.sleep(1.)

    for i in range(n):
        client0.control_node('mynode{}'.format(i), 'stop').result()


    for i in range(n):
        client0.delete_node('mynode{}'.format(i)).result()
    
    #time.sleep(1.)
    
    
    
    
    process_nodegroup0.stop()


def test_cannot_stop_running_node():
    name, addr = 'nodegroup', 'tcp://127.0.0.1:6000'
    process_nodegroup0  = ProcessSpawner(NodeGroup,  name, addr)
    client0 = RPCClient(name, addr)
    
    client0.create_node('mynode', '_MyTestNode').result()
    client0.control_node('mynode', 'start').result()
    

    with pytest.raises(RemoteCallException):
        # a running node cannot be delete
        client0.delete_node('mynode').result()

    process_nodegroup0.stop()

if __name__ == '__main__':
    test_nodegroup0()
    test_cannot_stop_running_node()

