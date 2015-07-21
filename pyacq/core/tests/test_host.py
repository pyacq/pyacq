import time
import logging

from pyacq.core.host import Host
from pyacq.core.processspawner import ProcessSpawner
from pyacq.core.rpc import RPCClient

logging.getLogger().level=logging.INFO


def test_host1():
    
    process_host0  = ProcessSpawner(Host,  'host0', 'tcp://127.0.0.1:*')
    process_host1  = ProcessSpawner(Host,  'host1', 'tcp://127.0.0.1:*')
    
    client0 = RPCClient('host0', process_host0.addr)
    print('on ping: ', client0.ping())
    
    time.sleep(1.)
    
    process_host0.stop()
    process_host1.stop()


def test_host2():
    
    process_host0  = ProcessSpawner(Host,  'host0', 'tcp://127.0.0.1:*')
    
    client0 = RPCClient('host0', process_host0.addr)
    
    client0.new_nodegroup('nodegroup 0.1', 'tcp://127.0.0.1:*')
    client0.new_nodegroup('nodegroup 0.2', 'tcp://127.0.0.1:*')
    
    time.sleep(2.)
    
    client0.close_nodegroup('nodegroup 0.1')
    client0.close_nodegroup('nodegroup 0.2')
    
    time.sleep(1.)
    
    process_host0.stop()



if __name__ == '__main__':
    test_host1()
    test_host2()