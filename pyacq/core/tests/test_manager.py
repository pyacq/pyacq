import logging
import time
from pyacq.core import Manager, Host, create_manager
from pyacq.core.processspawner import ProcessSpawner
from pyacq.core.rpc import RPCClient
import os

#~ logging.getLogger().level=logging.INFO


def basic_test_manager():
    # Create a local Host to communicate with
    test_host = ProcessSpawner(Host, name='test-host', addr='tcp://127.0.0.1:*')
    host_cli = RPCClient(test_host.name, test_host.addr)
    
    
    mgr = ProcessSpawner(Manager, name='manager', addr='tcp://127.0.0.1:*')
    mcli = RPCClient(mgr.name, mgr.addr)
    
    # test connection to host
    host_name = test_host.name
    mcli.connect_host(host_name, test_host.addr)
    assert mcli.list_hosts() == [host_name]
    
    # create nodegroup and nodes
    assert mcli.list_nodegroups(host_name) == []
    mcli.create_nodegroup(host_name, 'nodegroup1')
    assert mcli.list_nodegroups(host_name) == ['nodegroup1']

    assert mcli.list_nodes('nodegroup1') == []
    mcli.create_node('nodegroup1', 'node1', '_MyTestNode')
    assert mcli.list_nodes('nodegroup1') == ['node1']
    mcli.control_node('node1', 'start')
    mcli.control_node('node1', 'stop')
    mcli.delete_node('node1')
    assert mcli.list_nodes('nodegroup1') == []
    
    mcli.close()
    host_cli.close()


def create_some_node_group(man):
    nodegroups = []
    for i in range(5):
        nodegroup = man.create_nodegroup(name = 'nodegroup{}'.format(i))
        nodegroup.register_node_type_from_module('pyacq.core.tests.fakenodes', 'FakeSender' )
        nodegroup.register_node_type_from_module('pyacq.core.tests.fakenodes', 'FakeReceiver' )
        nodegroups.append(nodegroup)
        
        sender = nodegroup.create_node('FakeSender', name = 'sender{}'.format(i))
        sender.configure()
        stream_spec = dict(protocol = 'tcp', interface = '127.0.0.1', port = '*',
                            transfertmode = 'plaindata', streamtype = 'analogsignal',
                            dtype = 'float32', shape = (-1, 16), compression ='',
                            scale = None, offset = None, units = '' )
        sender.outputs['signals'].configure(**stream_spec)
        sender.initialize()

        receivers = [nodegroup.create_node('FakeReceiver', name = 'receiver {} {}'.format(i,j)) for j in range(3)]
        for receiver in receivers:
            receiver.configure()
            receiver.input.connect(sender.output)
            receiver.initialize()
    
    return nodegroups
    
def test_close_manager_explicit():
    man = create_manager(auto_close_at_exit = False)
    nodegroups = create_some_node_group(man)
    
    for ng in nodegroups:
        ng.start_all_nodes()
    time.sleep(1.)
    for ng in nodegroups:
        ng.stop_all_nodes()
    
    man.close()
    time.sleep(4.)

def test_close_manager_implicit():
    man = create_manager(auto_close_at_exit = True)
    nodegroups = create_some_node_group(man)
    
    for ng in nodegroups:
        ng.start_all_nodes()
    time.sleep(1.)
    for ng in nodegroups:
        ng.stop_all_nodes()
    
    time.sleep(4.)

if __name__ == '__main__':
    basic_test_manager()
    test_close_manager_explicit()
    test_close_manager_implicit()
