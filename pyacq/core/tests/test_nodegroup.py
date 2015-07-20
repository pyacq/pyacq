import time
import pytest
import logging

from pyacq.core.rpc import RPCClient, RemoteCallException
from pyacq.core.processspawner import ProcessSpawner
from pyacq.core.nodegroup import NodeGroup
from pyacq.core.node import Node

#logging.basicConfig(level=logging.INFO)

def test_nodegroup0():
    name, addr = 'nodegroup', 'tcp://127.0.0.1:6000'
    process_nodegroup0  = ProcessSpawner(NodeGroup,  name, addr)
    client0 = RPCClient(name, addr)
    
    n = 5
    
    for i in range(n):
        client0.create_node('mynode{}'.format(i), '_MyTestNode')

    for i in range(n):
        client0.control_node('mynode{}'.format(i), 'start')

    for i in range(n):
        client0.control_node('mynode{}'.format(i), 'stop')

    for i in range(n):
        client0.delete_node('mynode{}'.format(i))
    
    process_nodegroup0.stop()


def test_cannot_delete_node_while_running():
    name, addr = 'nodegroup', 'tcp://127.0.0.1:6000'
    process_nodegroup0  = ProcessSpawner(NodeGroup,  name, addr)
    client0 = RPCClient(name, addr)
    
    client0.create_node('mynode', '_MyTestNode')
    client0.control_node('mynode', 'start')
    
    with pytest.raises(RemoteCallException):
        # a running node cannot be delete
        client0.delete_node('mynode')

    process_nodegroup0.stop()

def test_qwidget_node():
    name, addr = 'nodegroup0', 'tcp://127.0.0.1:6000'
    process_nodegroup0  = ProcessSpawner(NodeGroup,  name, addr)
    client0 = RPCClient(name, addr)
    client0.create_node('mynode', '_MyTestNodeQWidget')
    client0.control_node('mynode', 'show')
    
    name, addr = 'nodegroup1', 'tcp://127.0.0.1:6001'
    process_nodegroup1  = ProcessSpawner(NodeGroup,  name, addr)
    client1 = RPCClient(name, addr)
    client1.create_node('mynode', '_MyTestNodeQWidget')
    client1.control_node('mynode', 'show')
    
    time.sleep(5.)
    
    process_nodegroup0.stop()
    process_nodegroup1.stop()




if __name__ == '__main__':
    #~ test_nodegroup0()
    #~ test_cannot_delete_node_while_running()
    test_qwidget_node()

