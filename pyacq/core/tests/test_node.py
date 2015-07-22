import time

from pyacq import create_manager
from pyacq.core.node import Node

def test_stream_between_node():
    # this is done a NodeGroup level for testing
    man = create_manager()
    nodegroup = man.create_nodegroup()
    
    nodegroup.register_node_from_module('pyacq.core.tests.fakenodes', 'FakeSender' )
    nodegroup.register_node_from_module('pyacq.core.tests.fakenodes', 'FakeReceiver' )
    
    # create ndoes
    sender = nodegroup.create_node('FakeSender', name = 'sender')
    stream_dict = dict(protocol = 'tcp', interface = '127.0.0.1', port = '9000',
                        transfertmode = 'plaindata', streamtype = 'analogsignal',
                        dtype = 'float32', shape = (-1, 16), compression ='',
                        scale = None, offset = None, units = '' )
    sender.configure(sample_interval = 0.001)
    sender.create_outputs([ stream_dict ])
    sender.initialize()
    
    receiver = nodegroup.create_node('FakeReceiver', name = 'receiver')
    receiver.configure()
    receiver.set_inputs([ stream_dict ])
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

    



    
    
if __name__ == '__main__':
    test_stream_between_node()
    #~ test_stream_between_node2()
    





