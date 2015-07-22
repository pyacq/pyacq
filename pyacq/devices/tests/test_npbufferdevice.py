import time

from pyacq import create_manager

import logging
#~ logging.getLogger().level=logging.INFO

import atexit


def test_npbufferdevice():
    man = create_manager()
    nodegroup = man.create_nodegroup()
    
    dev = nodegroup.create_node('NumpyDeviceBuffer', name = 'dev')
    dev.configure( nb_channel = 16, sample_interval = 0.001)
    stream_dict = dict(protocol = 'tcp', interface = '127.0.0.1', port = '9000',
                        transfertmode = 'plaindata', streamtype = 'analogsignal',
                        dtype = 'float32', shape = (-1, 16), compression ='',
                        scale = None, offset = None, units = '' )
    dev.create_outputs([ stream_dict ])    
    dev.initialize()
    
    
    
    # create some receveiver
    receiver_names = [ 'receiver{}'.format(i) for i in range(3) ]
    
    # create stream
    receivers = [ nodegroup.create_node('_MyReceiverNode', name = 'receiver{}'.format(i)) for i in range(3) ]
    for receiver in receivers:
        receiver.configure()
        receiver.set_inputs([ stream_dict ])
        receiver.initialize()
    
    nodegroup.start_all()
    
    print(nodegroup.any_node_running())
    time.sleep(5.)
    
    nodegroup.stop_all()
    print(nodegroup.any_node_running())

    man.default_host().close()
    man.close()


if __name__ == '__main__':
    test_npbufferdevice()

 
