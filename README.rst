====
pyacq
====

pyacq is a pure python simple framework for data acquisition.
By data we mean : analog signal, digital signal, video, event.
pyacq use zmq and so offer a simple to distribute data across thread, process and machine
to build more complex acquisition system.

pyacq implement a simple layer to inteact with some hardware device. For the list the list short:
    * on linux : all comedi device
    * on windows : measurement computing device with Universal Library
    * on linx/win the Emotiv EEg system.
    
pyacq also propose some basic visualisation with Qt4 widget to be embeded in Qt application:
   * a simple but multi signal oscilloscope
   * a online multisignal time frequency 




More information
----------------

- github: http://neuralensemble.org/neo
- Mailing list: https://groups.google.com/forum/?fromgroups#!forum/neuralensemble
- Documentation: http://packages.python.org/pyacq/

For installation instructions, see doc/source/install.rst

:copyright: Copyright 2010-2012 by the pyacq team, see AUTHORS.
:license: Modified BSD License, see LICENSE.txt for details.
