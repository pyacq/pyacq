import time
import logging

from pyacq.core.rpc import RPCClient, ProcessSpawner

#~ logging.getLogger().level=logging.INFO


def test_host1():
    
    proc1 = ProcessSpawner()
    host1 = proc1.client._import('pyacq').Host('host1')
    proc2 = ProcessSpawner()
    host2 = proc1.client._import('pyacq').Host('host1')
    
    ng11 = host1.create_nodegroup()
    ng12 = host1.create_nodegroup()
    ng21 = host2.create_nodegroup()
    ng22 = host2.create_nodegroup()

    host1.close_all_nodegroups()
    ng22.stop_all_nodes()
    host2.close_all_nodegroups()
    
    proc1.stop()
    proc2.stop()




if __name__ == '__main__':
    test_host1()
    test_host2()
