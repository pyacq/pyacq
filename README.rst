====
pyacq
====

pyacq is a pure python simple framework for data acquisition.
By data we mean : analog signal, digital signal, video, event.
pyacq use zmq and so offer a simple to distribute data across thread, process and machine
to build more complex acquisition system.

pyacq implement a simple layer to inteact with some hardware device. Here the list:
    * on linux : all comedi device
    * on windows : measurement computing device with Universal Library
    * on linux/win : the Emotiv EEG system.
    * on linux/win : the brainvision EEG with the socket.
    
pyacq also propose some basic visualisation with Qt4 widget to be embeded in Qt application:
   * a simple but multi signal continuous oscilloscope.
   * a online multisignal time frequency 
   * a multi signal oscilloscope in triggered mode.




More information
----------------

- github: https://github.com/samuelgarcia/pyacq
- Mailing list: 
- Documentation: http://packages.python.org/pyacq/

For installation instructions, see doc/source/install.rst

:copyright: Copyright 2010-2012 by the pyacq team, see AUTHORS.
:license: Modified BSD License, see LICENSE.txt for details.
