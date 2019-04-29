=====
pyacq
=====

<a href="https://travis-ci.org/pyacq/pyacq"><img src="https://travis-ci.org/pyacq/pyacq.svg?branch=master"></a>
[![Build status](https://ci.appveyor.com/api/projects/status/ynioa3acql26mo96?svg=true)](https://ci.appveyor.com/project/samuelgarcia/pyacq-fxy8y)

Pyacq is a simple, pure-Python framework for distributed data acquisition and
stream processing. Its primary use cases are for analog signals, digital
signals, video, and events. Pyacq uses ZeroMQ to stream data between
distributed threads, processes, and machines to build more complex and
scalable acquisition systems.


Supported Hardware
------------------

|                                       |  Linux  | Windows |
|:--------------------------------------|:-------:|:-------:|
| National Instruments devices (DAQmx)  |    ?    |    X    |
| Measurement Computing  |        |    X    |
| Scientific cameras (via MicroManager) |    X    |    X    |
| Emotiv EEG system                     |    X    |    X    |
| BrainVision EEG                       |    X    |    X    |
| Audio interfaces (via PyAudio)        |    X    |    X    |
| Webcams (via imageio or libav)        |    X    |    X    |
| Blackrock NSP        |        |    X    |


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
- License: Distributed under BSD 3-clause license, see LICENSE for details. 
- Installation: http://pyacq.readthedocs.org/en/latest/intro.html#installation


Copyright (c) 2016, French National Center for Scientific Research (CNRS).


