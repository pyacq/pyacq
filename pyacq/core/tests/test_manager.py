import logging
import time
from pyacq.core import Manager, create_manager
from pyacq.core.host import Host
from pyacq.core.rpc import ProcessSpawner
import os
import pytest


logger = logging.getLogger()


def test_manager():
    #logger.level = logging.DEBUG
    mgr = create_manager('rpc')
    
    # Create a local Host to communicate with
    host_proc, host = Host.spawn('test-host')
    host_addr = host_proc.client.address
    
    # test connection to host
    host = mgr.get_host(host_addr)
    assert mgr.list_hosts() == [host]
    
    # create nodegroup 
    assert mgr.list_nodegroups() == []
    ng1 = mgr.create_nodegroup('nodegroup1', host)
    assert mgr.list_nodegroups() == [ng1]
    

    assert ng1.list_nodes() == []
    n1 = ng1.create_node('_MyTestNode')
    assert ng1.list_nodes() == [n1]
    n1.initialize()
    n1.configure()
    n1.start()
    n1.stop()
    ng1.remove_node(n1)
    assert ng1.list_nodes() == []


def create_some_node_group(man):
    nodegroups = []
    for i in range(5):
        nodegroup = man.create_nodegroup(name='nodegroup{}'.format(i))
        nodegroup.register_node_type_from_module('pyacq.core.tests.fakenodes', 'FakeSender')
        nodegroup.register_node_type_from_module('pyacq.core.tests.fakenodes', 'FakeReceiver')
        nodegroups.append(nodegroup)
        
        sender = nodegroup.create_node('FakeSender', name='sender{}'.format(i))
        sender.configure()
        stream_spec = dict(protocol='tcp', interface='127.0.0.1', port='*',
                            transfertmode='plaindata', streamtype='analogsignal',
                            dtype='float32', shape=(-1, 16), compression ='',
                            scale = None, offset = None, units = '')
        sender.outputs['signals'].configure(**stream_spec)
        sender.initialize()

        receivers = [nodegroup.create_node('FakeReceiver', name='receiver {} {}'.format(i,j)) for j in range(3)]
        for receiver in receivers:
            receiver.configure()
            receiver.input.connect(sender.output)
            receiver.initialize()
    
    return nodegroups
    

def test_close_manager_explicit():
    #logging.getLogger().level = logging.DEBUG
    man = create_manager(auto_close_at_exit=False)
    nodegroups = create_some_node_group(man)
    
    for ng in nodegroups:
        ng.start_all_nodes()
    time.sleep(1.)
    for ng in nodegroups:
        ng.stop_all_nodes()
    
    man.close()
    #time.sleep(2.)


#@pytest.mark.skipif(True, reason='atexit not work at travis')
#def test_close_manager_implicit():
    #man = create_manager(auto_close_at_exit=True)
    #nodegroups = create_some_node_group(man)
    
    #for ng in nodegroups:
        #ng.start_all_nodes()
    #time.sleep(1.)
    #for ng in nodegroups:
        #ng.stop_all_nodes()
    
    #time.sleep(2.)

if __name__ == '__main__':
    test_manager()
    test_close_manager_explicit()
    test_close_manager_implicit()
