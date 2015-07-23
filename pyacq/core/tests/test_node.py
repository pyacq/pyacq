import time

from pyacq import create_manager
from pyacq.core.node import Node

def test_stream_between_node():
    # this is done at Node level the manager do not known the connection
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
    # this is done at Manager level the manager do known the connection
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
    #man.create_node_outputs(sender, [streamdef0])
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

def test_visual_node_both_in_main_qapp_and_remote_qapp():
    man = create_manager()
    nodegroup = man.create_nodegroup()
    
    nodegroup.register_node_from_module('pyacq.core.tests.fakenodes', 'FakeSender' )
    nodegroup.register_node_from_module('pyacq.core.tests.fakenodes', 'ReceiverWidget' )


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
    
    #receiver0 is in remote QApp (in nodegroup)
    receiver0 = nodegroup.create_node('ReceiverWidget', name = 'receiver0', tag ='I am in distant QApp')
    receiver0.configure()
    receiver0.set_inputs([ streamdef0 ])
    receiver0.initialize()
    receiver0.show()
    
    
    #receiver1 is in local QApp
    from pyqtgraph.Qt import QtCore, QtGui
    from pyacq.core.tests.fakenodes import ReceiverWidget
    app = QtGui.QApplication([])
    receiver1 = ReceiverWidget(name = 'receiver1', tag ='I am in local QApp')
    receiver1.configure()
    receiver1.set_inputs([ streamdef0 ])
    receiver1.initialize()
    receiver1.show()
    
    # start them for a while
    sender.start()
    receiver0.start()
    receiver1.start()
    print(nodegroup.any_node_running())
    
    app.exec_()
    
    time.sleep(2.)
    
    sender.stop()
    receiver0.stop()
    receiver1.stop()
    print(nodegroup.any_node_running())
    
    nodegroup.close()
    man.default_host().close()
    man.close()
    

if __name__ == '__main__':
    #~ test_stream_between_node()
    #~ test_stream_between_node2()
    test_visual_node_both_in_main_qapp_and_remote_qapp()





