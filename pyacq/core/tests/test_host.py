import time

from pyacq.core.host import Host
from pyacq.core.processspawner import ProcessSpawner
from pyacq.core.rpc import RPCClient

def test_host1():
    
    process_host0  = ProcessSpawner(Host,  'host0', 'tcp://127.0.0.1:5406')
    process_host1  = ProcessSpawner(Host,  'host1', 'tcp://127.0.0.1:5407')
    
    client0 = RPCClient('host0', 'tcp://127.0.0.1:5406')
    print('on ping: ', client0.ping().result())
    
    time.sleep(1.)
    
    process_host0.stop()
    process_host1.stop()


def test_host2():
    
    process_host0  = ProcessSpawner(Host,  'host0', 'tcp://127.0.0.1:5406')
    
    client0 = RPCClient('host0', 'tcp://127.0.0.1:5406')
    
    client0.new_nodegroup('nodegroup 0.1', 'tcp://127.0.0.1:6000').result()
    client0.new_nodegroup('nodegroup 0.2', 'tcp://127.0.0.1:6001').result()
    
    time.sleep(2.)
    
    client0.close_nodegroup('nodegroup 0.1').result()
    client0.close_nodegroup('nodegroup 0.2').result()
    
    time.sleep(1.)
    
    process_host0.stop()



if __name__ == '__main__':
    test_host1()
    test_host2()