import time
import sys
from pyacq import create_manager

from pyqtgraph.Qt import QtCore, QtGui
import pyqtgraph as pg
from pyacq.core.tests.fakenodes import FakeSender, FakeReceiver, ReceiverWidget

import logging
#~ logging.getLogger().level=logging.INFO


def test_stream_between_local_nodes():
    # create local nodes in QApplication
    app = pg.mkQApp()

    sender = FakeSender()
    stream_spec = dict(protocol='tcp', interface='127.0.0.1', port='*',
                        transfertmode='plaindata', streamtype='analogsignal',
                        dtype='float32', shape=(-1, 16), compression ='',
                        scale = None, offset = None, units = '')
    sender.configure(sample_interval=0.001)
    sender.outputs['signals'].configure(**stream_spec)
    # sender.output.configure(**stream_spec)
    sender.initialize()
    
    receiver = FakeReceiver()
    receiver.configure()
    receiver.inputs['signals'].connect(sender.outputs['signals'])
    # receiver.input.connect(sender.output)
    receiver.initialize()
    
    # start them for a while
    sender.start()
    receiver.start()
    
    def terminate():
        sender.stop()
        receiver.stop()
        app.quit()
        
    timer = QtCore.QTimer(singleShot=True, interval=3000)
    timer.timeout.connect(terminate)
    timer.start()
    
    app.exec_()
    

def test_stream_between_remote_nodes():
    # this is done at Manager level the manager do known the connection
    man = create_manager(auto_close_at_exit=False)
    nodegroup = man.create_nodegroup('nodegroup')
    
    nodegroup.register_node_type_from_module('pyacq.core.tests.fakenodes', 'FakeSender')
    nodegroup.register_node_type_from_module('pyacq.core.tests.fakenodes', 'FakeReceiver')
    
    # create ndoes
    sender = nodegroup.create_node('FakeSender', name='sender')
    stream_spec = dict(protocol='tcp', interface='127.0.0.1', port='*',
                       transfertmode='plaindata', streamtype='analogsignal',
                       dtype='float32', shape=(-1, 16), compression='',
                       scale=None, offset=None, units='')
    sender.configure(sample_interval=0.001)
    sender.outputs['signals'].configure(**stream_spec)
    sender.initialize()
    
    receiver = nodegroup.create_node('FakeReceiver', name='receiver')
    receiver.configure()
    receiver.inputs['signals'].connect(sender.outputs['signals'])
    receiver.initialize()
    
    # start them for a while
    sender.start()
    receiver.start()
    print(nodegroup.any_node_running())
    
    time.sleep(2.)
    
    sender.stop()
    receiver.stop()
    print(nodegroup.any_node_running())
    
    man.close()


def test_stream_between_local_and_remote_nodes():
    # this is done at Manager level the manager do known the connection
    man = create_manager(auto_close_at_exit=False)
    nodegroup = man.create_nodegroup('nodegroup')
    
    nodegroup.register_node_type_from_module('pyacq.core.tests.fakenodes', 'FakeSender')
    
    # create ndoes
    sender = nodegroup.create_node('FakeSender', name='sender')
    stream_spec = dict(protocol='tcp', interface='127.0.0.1', port='*',
                        transfertmode='plaindata', streamtype='analogsignal',
                        dtype='float32', shape=(-1, 16), compression ='',
                        scale = None, offset = None, units = '')
    sender.configure(sample_interval=0.001)
    sender.output.configure(**stream_spec)
    sender.initialize()
    
    # create local nodes in QApplication
    app = pg.mkQApp()
    
    receiver = FakeReceiver()
    receiver.configure()
    receiver.input.connect(sender.output)
    receiver.initialize()
    
    # start them for a while
    sender.start()
    receiver.start()

    def terminate():
        sender.stop()
        receiver.stop()
        app.quit()
        
    timer = QtCore.QTimer(singleShot=True, interval=2000)
    timer.timeout.connect(terminate)
    timer.start()
    
    app.exec_()
    
    man.close()
    



def test_visual_node_both_in_main_qapp_and_remote_qapp():
    man = create_manager(auto_close_at_exit=False)
    nodegroup = man.create_nodegroup('nodegroup')
    
    nodegroup.register_node_type_from_module('pyacq.core.tests.fakenodes', 'FakeSender')
    nodegroup.register_node_type_from_module('pyacq.core.tests.fakenodes', 'ReceiverWidget')


    # create ndoes
    sender = nodegroup.create_node('FakeSender', name='sender')
    stream_spec = dict(protocol='tcp', interface='127.0.0.1', port='*',
                        transfertmode='plaindata', streamtype='analogsignal',
                        dtype='float32', shape=(-1, 16), compression ='',
                        scale = None, offset = None, units = '')
    sender.configure(sample_interval=0.001)
    sender.output.configure(**stream_spec)
    sender.initialize()
    
    # receiver0 is in remote QApp (in nodegroup)
    receiver0 = nodegroup.create_node('ReceiverWidget', name='receiver0', tag='<b>I am in distant QApp</b>')
    receiver0.configure()
    receiver0.input.connect(sender.output)
    receiver0.initialize()
    receiver0.show()
    
    
    # receiver1 is in local QApp
    app = pg.mkQApp()
    receiver1 = ReceiverWidget(name='receiver1', tag='<b>I am in local QApp</b>')
    receiver1.configure()
    receiver1.input.connect(sender.output)
    receiver1.initialize()
    receiver1.show()
    
    # start them for a while
    sender.start()
    receiver0.start()
    receiver1.start()
    print(nodegroup.any_node_running())

    def terminate():
        sender.stop()
        receiver0.stop()
        receiver1.stop()
        receiver1.close()
        app.quit()
        
    timer = QtCore.QTimer(singleShot=True, interval=1000)
    timer.timeout.connect(terminate)
    timer.start()
    
    app.exec_()
    
    receiver0.close()
    man.close()
    
    

if __name__ == '__main__':
    test_stream_between_local_nodes()
    test_stream_between_remote_nodes()
    test_stream_between_local_and_remote_nodes()
    test_visual_node_both_in_main_qapp_and_remote_qapp()


