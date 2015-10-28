import time
import logging

from pyacq.core.host import HostSpawner

#~ logging.getLogger().level=logging.INFO


def test_host1():
    
    host1 = HostSpawner('host1')
    host2 = HostSpawner('host2')
    
    ng11 = host1.create_nodegroup()
    ng12 = host1.create_nodegroup()
    ng21 = host2.create_nodegroup()
    ng22 = host2.create_nodegroup()

    host1.close_all_nodegroups()
    ng22.stop_all_nodes()
    host2.close_all_nodegroups()
    
    host1.stop()
    host2.stop()




if __name__ == '__main__':
    test_host1()
    test_host2()
