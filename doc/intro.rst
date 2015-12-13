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

Code examples


Architecture
------------

Pyacq consists of 1) a collection of nodes with various capabilities for 
acquisition, processing, and visualization, and 2) a set of core tools that
facilitate distributed control and data streaming.
    
    


Overview of node types
----------------------



Acquisition nodes: pyaudio, webcam, ...
Processing nodes:  spikesorter?
Visualization nodes: oscilloscope, qtimefreq, ...



