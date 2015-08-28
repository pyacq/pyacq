import time

from pyacq import create_manager

#~ import logging
#~ logging.getLogger().level=logging.INFO


def test_npbufferdevice():
    man = create_manager()
    nodegroup = man.create_nodegroup()
    
    dev = nodegroup.create_node('NumpyDeviceBuffer', name = 'dev')
    dev.configure( nb_channel = 7, sample_interval = 0.0001)
    stream_dict = dict(protocol = 'tcp', interface = '127.0.0.1', port = '*',
                        transfertmode = 'plaindata', streamtype = 'analogsignal',
                        dtype = 'float32', shape = (-1, 16), compression ='',
                        scale = None, offset = None, units = '' )
    dev.output.configure(protocol = 'tcp', interface = '127.0.0.1', transfertmode = 'plaindata')
    dev.initialize()
    
    # create stream
    nodegroup.register_node_type_from_module('pyacq.core.tests.fakenodes', 'FakeReceiver' )
    receivers = [ nodegroup.create_node('FakeReceiver', name = 'receiver{}'.format(i)) for i in range(3) ]
    for receiver in receivers:
        receiver.configure()
        receiver.input.connect(dev.output)
        receiver.initialize()
    
    nodegroup.start_all_nodes()
    
    print(nodegroup.any_node_running())
    time.sleep(1.)
    
    nodegroup.stop_all_nodes()
    print(nodegroup.any_node_running())
    
if __name__ == '__main__':
    test_npbufferdevice()

 
