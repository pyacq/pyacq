import time
import pytest
import logging

from pyacq.core.rpc import RemoteCallException
from pyacq.core.host import Host

from pyacq import create_manager


#~ logging.getLogger().level=logging.INFO

def test_nodegroup0():
    proc, host = Host.spawn('host1')
    ng = host.create_nodegroup('nodegroup')
    n = 5
    nodes = [ng.create_node('_MyTestNode', name='mynode{}'.format(i)) for i in range(n)]

    for i in range(n):
        nodes[i].configure()

    for i in range(n):
        nodes[i].initialize()

    for i in range(n):
        nodes[i].start()

    with pytest.raises(RemoteCallException):
        # a running node cannot be delete
        ng.remove_node(nodes[0])
        
    for i in range(n):
        nodes[i].stop()

    # test qwidget display
    qt_node = ng.create_node('_MyTestNodeQWidget', name='myqtnode')
    qt_node.show()
    
    for i in range(n):
        ng.remove_node(nodes[i])
    
    ng.close()


if __name__ == '__main__':
    test_nodegroup0()


