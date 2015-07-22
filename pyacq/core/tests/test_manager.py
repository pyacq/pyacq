import logging
from pyacq.core import Manager, Host
from pyacq.core.processspawner import ProcessSpawner
from pyacq.core.rpc import RPCClient

logging.getLogger().level=logging.INFO

# Create a local Host to communicate with
test_host = ProcessSpawner(Host, name='test-host', addr='tcp://127.0.0.1:*')


def test_manager():
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

    
if __name__ == '__main__':
    test_manager()
