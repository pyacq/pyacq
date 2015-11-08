import time
import logging

from pyacq.core.host import Host

#~ logging.getLogger().level=logging.INFO


def test_host1():
    
    p1, host1 = Host.spawn('host1')
    p2, host2 = Host.spawn('host2')
    
    ng11 = host1.create_nodegroup('ng1')
    ng12 = host1.create_nodegroup('ng2')
    ng21 = host2.create_nodegroup('ng3')
    ng22 = host2.create_nodegroup('ng4')

    assert len(host1.spawners) == 2
    host1.close_all_nodegroups()
    assert len(host1.spawners) == 0
    host2.close_all_nodegroups()
    assert len(host2.spawners) == 0
    
    p1.stop()
    p2.stop()


if __name__ == '__main__':
    test_host1()
    test_host2()
