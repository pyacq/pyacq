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


def test_register_node_type_from_module():
    man = create_manager(auto_close_at_exit=False)
    nodegroup = man.create_nodegroup('nodegroup')
    
    nodegroup.register_node_type_from_module('pyacq.core.tests.fakenodes', 'NoneRegisteredClass')
    node = nodegroup.create_node('NoneRegisteredClass')
    
    man.close()
    
"""
class MyNewNode(Node):
    pass

def test_register_node_with_pickle():
    man = create_manager()
    nodegroup = man.create_nodegroup()
    import pickle
    picklizedclass = pickle.dumps(MyNewNode)
    print(picklizedclass)
    nodegroup.register_node_with_pickle(picklizedclass, 'MyNewNode')
    nodegroup.create_node( 'MyNewNode')
"""

if __name__ == '__main__':
    test_nodegroup0()
    bench_ping_pong_nodegroup()
    test_cannot_delete_node_while_running()
    test_remotly_show_qwidget_node()
    test_register_node_type_from_module()
    # test_register_node_with_pickle()  ### not working at the moment

