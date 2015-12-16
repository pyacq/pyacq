Introduction
============

What is Pyacq?
--------------

Pyacq is an open-source system for distributed data acquisition and stream
processing. Its functionality is organized into nodes that individually handle
acquisition, filtering, visualization, and recording. Nodes are created on
demand and connected to form a graph of data streams. Nodes may be created and
connected within a single thread, or distributed across multiple threads,
processes, and hosts.

Example use case

  [figure: EEG input -> filter -> online analysis -> viewer, recorder]

Code example::

    import pyacq
    
    manager = pyacq.create_manager('rpc')
    worker_host = manager.add_host('tcp://10.0.0.103:5678')
    worker = worker_host.create_nodegroup()
    
    device = manager.create_node('BrainAmpSocket')
    analyzer = worker.create_node('Spikesorter')
    recorder = worker.create_node('HDF5Recorder')
    viewer = pyacq.QOscilloscope()
    
    analyzer.input.connect(device.output)
    recorder.input.connect(analyzer.output)
    viewer.input.connect(analyzer.output)
    
    manager.start_all()
    


Architecture
------------

Pyacq consists of 1) a collection of nodes with various capabilities for 
acquisition, processing, and visualization, and 2) a set of core tools that
facilitate distributed control and data streaming.
    
    


Overview of node types
----------------------


============================================= ==================================== ==================================================
**Acquisition**                               **Processing**                       **Visualization**
--------------------------------------------- ------------------------------------ --------------------------------------------------
:ref:`PyAudio <PyAudio_node>`                 :ref:`Triggering <triggering_nodes>` :ref:`Oscilloscope <analog_viewer_nodes>`
:ref:`Webcam (libav, imageio) <camera_nodes>`                                      :ref:`Wavelet spectrogram <spectral_viewer_nodes>`
:ref:`BrainAmp <BrainAmp_node>`                                                    
:ref:`Emotiv <Emotiv_node>`
============================================= ==================================== ==================================================



