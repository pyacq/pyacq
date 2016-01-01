.. currentmodule:: pyacq.core


Data streams
============

As data is acquired in Pyacq, it is transmitted from Node to Node within the
:ref:`graph <introduction>` using :ref:`Stream classes <api_streams>`. Each Node
has one or more input and/or output streams that may be connected together, and
each stream can be configured to transmit different types and shapes of data::
    
    device.output.configure(protocol='tcp', interface='127.0.0.1', 
                            transfertmode='plaindata')
    viewer.input.connect(device.output)
    recorder.input.connect(device.output)    

For the most part, Nodes will automatically decide the configuration options for
their input/output streams based on the data they receive or generate. 
Some options, however, must be configured manually. In the
sections below we describe the basic operating theory for streams and the
associated configuration options.


Streamable Data Types
'''''''''''''''''''''

Pyacq's streams can, in principle, carry any type of time-varying signal that
can be represented by a numpy array. In practice, this is expressed in a
few simple cases:
    
* One or more analog signals such as an audio stream or multichannel
  EEG data. If multiple signals are transmitted in a single stream, they must
  be time-locked such that, for each time point represented in the data, every
  channel must have exactly one value recorded (in other words, it must be
  possible to represent the data as a 2D array of floating-point values).
* One or more time-locked digital signals. These are typically recorded TTL
  signals such as a lever-press indicator or the frame exposure signal from a
  camera.
* A video feed from a camera. Although it would be possible to carry multiple
  time-locked video signals in a single stream, this might be more naturally
  implemented by creating a single stream per video feed.
* A stream of events, where each event is a ``(time, value)`` pair that
  indicates the time that the event occurred and an integer descriptor of the
  event. This can be used in a similar way to digital signals (for recording
  button presses, beam crossings, etc.), but where the events are sparsely
  coded and the complete sample-by-sample recording of the digital signal is
  either unnecessary or unavailable.

Streams can be used to transmit multidimensional arrays, and for the most part,
the shape of these arrays is left to the user to decide. The only requirement
is that the first array axis should represent time. Conceptually, stream data
represents an array where axis 0 can have an arbitrary length that grows over
time as data is collected. In practice, this data is represented in chunks 
as numpy arrays with a fixed size for axis 0.


Data Transmission
'''''''''''''''''

Data transmission through a stream occurs in several stages:
    
1. **Pre-filtering:** As data is passed to an output stream, it is passed through an arbitrary
   sequence of filtering functions. These are used, for example, to scale, cast,
   or reshape data as needed to meet the stream requirements.
2. **Chunking:** The output stream collects data until a minimum chunk size is reached. The 
   chunk size is determined by the :func:`output stream configuration <OutputStream.configure>`
   and may depend on the data type. For example, a 100 kHz analog
   signal might be transmitted over a stream in 1000-sample chunks, whereas a
   video feed might be transmitted one frame at a time.
3. **Transmission:** The chunk is transmitted to all input streams that are connected to the
   output. The mechanism used to transmit data depends on the ``protocol`` and
   ``transfertmode`` arguments used during 
   :func:`output stream configuration <OutputStream.configure>`:
   
   * Plain data stream over TCP: data is sent by TCP using a ZeroMQ socket.
   * Plain data stream within process: data is sent using a ZeroMQ "inproc" socket,
     which avoids uncecessary memory copies.
   * Shared memory: data is written into shared memory, and the new memory
     pointer is sent using a TCP or inproc ZeroMQ socket.
     
4. **Reassembly:** Each connected input stream independently receives data chunks and
   reassembles the stream.
5. **Post-filtering:** The reconstructed stream data is passed through another arbitrary sequence
   of filtering functions before being made available to the stream user.

When transmitting plain data streams, Pyacq tries to maximize throughput by
avoiding any unnecessary data copies. In most cases, a copy is required only if
the input array does not occupy a contiguous block of memory.

.. seealso:: :func:`OutputStream.configure()` 


Using Streams in Custom Node Types
----------------------------------

Node classes are responsible for handling most of the configuration for their
input/output streams as well as for sending, receiving, and reconstructing data
through the streams. This functionality is mostly hidden from Node users;
however, if you plan to write custom Node classes, then it is
necessary to understand this process in more detail.

Node subclasses must declare their input and output streams through the
``_input_specs`` and ``_output_specs`` class attributes. Each attribute is a
dict whose keys are the names of the streams and whose values provide the
default configuration arguments for the stream.

[example]

how to piece together stream on the far end

example code
    
How to use poller threads


* How to specify input/output streams
* How to configure
