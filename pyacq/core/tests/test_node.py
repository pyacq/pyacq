import time

from pyacq import create_manager
from pyacq.core.node import Node

def test_stream_between_node():
    # this is done a Node level for testing
    man = create_manager()
    nodegroup = man.create_nodegroup()
    
    nodegroup.register_node_from_module('pyacq.core.tests.fakenodes', 'FakeSender' )
    nodegroup.register_node_from_module('pyacq.core.tests.fakenodes', 'FakeReceiver' )
    
    # create ndoes
    sender = nodegroup.create_node('FakeSender', name = 'sender')
    streamdef0 = dict(protocol = 'tcp', interface = '127.0.0.1', port = '9000',
                        transfertmode = 'plaindata', streamtype = 'analogsignal',
                        dtype = 'float32', shape = (-1, 16), compression ='',
                        scale = None, offset = None, units = '' )
    sender.configure(sample_interval = 0.001)
    sender.create_outputs([ streamdef0 ])
    sender.initialize()
    
    receiver = nodegroup.create_node('FakeReceiver', name = 'receiver')
    receiver.configure()
    receiver.set_inputs([ streamdef0 ])
    receiver.initialize()
    
    # start them for a while
    sender.start()
    receiver.start()
    print(nodegroup.any_node_running())
    
    time.sleep(3.)
    
    sender.stop()
    receiver.stop()
    print(nodegroup.any_node_running())
    
    nodegroup.close()
    man.default_host().close()
    man.close()


def test_stream_between_node2():
    # this is done a Node level for testing
    man = create_manager()
    nodegroup = man.create_nodegroup()
    
    nodegroup.register_node_from_module('pyacq.core.tests.fakenodes', 'FakeSender' )
    nodegroup.register_node_from_module('pyacq.core.tests.fakenodes', 'FakeReceiver' )
    
    # create ndoes
    sender = nodegroup.create_node('FakeSender', name = 'sender')
    streamdef0 = dict(protocol = 'tcp', interface = '127.0.0.1', port = '9000',
                        transfertmode = 'plaindata', streamtype = 'analogsignal',
                        dtype = 'float32', shape = (-1, 16), compression ='',
                        scale = None, offset = None, units = '' )
    sender.configure(sample_interval = 0.001)
    #~ sender.create_outputs([ streamdef0 ])
    man.create_node_outputs(sender.name, [streamdef0])
    sender.initialize()
    
    receiver = nodegroup.create_node('FakeReceiver', name = 'receiver')
    receiver.configure()
    receiver.set_inputs([ streamdef0 ])
    #~ man.set_node_inputs(receiver.name, [streamdef0])
    receiver.initialize()
    
    # start them for a while
    sender.start()
    receiver.start()
    print(nodegroup.any_node_running())
    
    time.sleep(2.)
    
    sender.stop()
    receiver.stop()
    print(nodegroup.any_node_running())
    
    nodegroup.close()
    man.default_host().close()
    man.close()
    
if __name__ == '__main__':
    #~ test_stream_between_node()
    test_stream_between_node2()
    





