# -*- coding: utf-8 -*-
# Copyright (c) 2016, French National Center for Scientific Research (CNRS)
# Distributed under the (new) BSD License. See LICENSE for more info.
"""
Noise generator node

Simple example of a custom Node class that generates a stream of random
values. 

"""
import numpy as np

from pyacq.core import Node, register_node_type
from pyqtgraph.Qt import QtCore, QtGui


class NoiseGenerator(Node):
    """A simple example node that generates gaussian noise.
    """
    _output_specs = {'signals': dict(streamtype='analogsignal', dtype='float32',
                                     shape=(-1, 1), compression='')}

    def __init__(self, **kargs):
        Node.__init__(self, **kargs)
        self.timer = QtCore.QTimer(singleShot=False)
        self.timer.timeout.connect(self.send_data)

    def _configure(self, chunksize=100, sample_rate=1000.):
        self.chunksize = chunksize
        self.sample_rate = sample_rate
        
        self.output.spec['shape'] = (-1, 1)
        self.output.spec['sample_rate'] = sample_rate
        self.output.spec['buffer_size'] = 1000

    def _initialize(self):
        self.head = 0
        
    def _start(self):
        self.timer.start(int(1000 * self.chunksize / self.sample_rate))

    def _stop(self):
        self.timer.stop()
    
    def _close(self):
        pass
    
    def send_data(self):
        self.head += self.chunksize
        self.output.send(np.random.normal(size=(self.chunksize, 1)).astype('float32'), index=self.head)


# Not necessary for this example, but registering the node class would make it
# easier for us to instantiate this type of node in a remote process via
# Manager.create_node()
register_node_type(NoiseGenerator)



if __name__ == '__main__':
    from pyacq.viewers import QOscilloscope
    app = QtGui.QApplication([])
    
    # Create a noise generator node
    ng = NoiseGenerator()
    ng.configure()
    ng.output.configure(protocol='inproc', transfermode='sharedmem')
    ng.initialize()
    
    # Create an oscilloscope node to view the noise stream
    osc = QOscilloscope()
    osc.configure(with_user_dialog=True)
    osc.input.connect(ng.output)
    osc.initialize()
    osc.show()

    # start both nodes
    osc.start()
    ng.start()
    