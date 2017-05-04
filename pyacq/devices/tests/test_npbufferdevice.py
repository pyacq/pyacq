import time

from pyacq import create_manager
import numpy as np

#~ import logging
#~ logging.getLogger().level=logging.INFO


def test_npbufferdevice():
    man = create_manager(auto_close_at_exit=False)
    nodegroup = man.create_nodegroup()
    
    #~ sigs = None
    sigs = np.random.randn(2560, 7).astype('float64')
    
    dev = nodegroup.create_node('NumpyDeviceBuffer', name='dev')
    dev.configure(nb_channel=7, sample_interval=0.0001, chunksize=256, buffer=sigs)
    dev.output.configure(protocol='tcp', interface='127.0.0.1', transfertmode='plaindata')
    dev.initialize()
    
    # create stream
    nodegroup.register_node_type_from_module('pyacq.core.tests.fakenodes', 'FakeReceiver')
    receivers = [nodegroup.create_node('FakeReceiver', name='receiver{}'.format(i)) for i in range(3)]
    for receiver in receivers:
        receiver.configure()
        receiver.input.connect(dev.output)
        receiver.initialize()
    
    nodegroup.start_all_nodes()
    
    #~ print(nodegroup.any_node_running())
    time.sleep(1.)
    
    nodegroup.stop_all_nodes()
    #~ print(nodegroup.any_node_running())
    
    man.close()
    
if __name__ == '__main__':
    test_npbufferdevice()

 
