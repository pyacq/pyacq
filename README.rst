=====
pyacq
=====

|Build Status| 

Version 0.1 is quite drafty.
A version 0.2 is in preparation (summer 2015).

Pyacq is a simple, pure-Python framework for distributed data acquisition and
stream processing. Its primary use cases are for analog signals, digital
signals, video, and events. Pyacq uses ZeroMQ to stream data between
distributed threads, processes, and machines to build more complex and
scalable acquisition systems.


Supported Hardware
------------------

  |                                       |  Linux  | Windows |
  |:--------------------------------------|:-------:|:-------:|
  | Audio interfaces (via PyAudio)        |    X    |    X    |
  | Webcams (via imageio or libav)        |    X    |    X    |
  | Scientific cameras (via MicroManager) |    X    |    X    |
  | Emotiv EEG system                     |    X    |    X    |
  | BrainVision EEG                       |    X    |    X    |
  | National Instruments devices (DAQmx)  |    ?    |    X    |
  
  
Visualization Tools
-------------------

* Multichannel continuous oscilloscope
* Multichannel triggered oscilloscope
* Wavelet spectrum analyzer
* Video display



More information
----------------

- Github: https://github.com/pyacq
- Mailing list: 
- Documentation: http://pyacq.readthedocs.org/en/latest/

For installation instructions, see http://pyacq.readthedocs.org/en/latest/intro.html#installation


:copyright: Copyright (c) 2016, French National Center for Scientific Research (CNRS).
:license: BSD 3-clause license, see LICENSE for details.


.. |Build Status| image:: https://travis-ci.org/pyacq/pyacq.svg?branch=master
   :target: https://travis-ci.org/pyacq/pyacq
