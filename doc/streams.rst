.. currentmodule:: pyacq.core

.. _streams:

Data streams
============

As data is acquired in Pyacq, it is transmitted from Node to Node within the
:ref:`graph <introduction>` using :ref:`Stream classes <apiref_streams>`. Each Node
has one or more input and/or output streams that may be connected together, and
each stream can be configured to transmit different types and shapes of data::
    
    device.output.configure(protocol='tcp', interface='127.0.0.1', 
                            transfermode='plaindata')
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
    
1. **Pre-filtering:** As data is passed to an output stream, it is passed through a user-defined
   sequence of filtering functions. These are used, for example, to scale, cast,
   or reshape data as needed to meet the stream requirements.
2. **Chunking:** The output stream collects data until a minimum chunk size is reached. The 
   chunk size is determined by the :func:`output stream configuration <OutputStream.configure>`
   and may depend on the data type. For example, a 100 kHz analog
   signal might be transmitted over a stream in 1000-sample chunks, whereas a
   video feed might be transmitted one frame at a time.
3. **Transmission:** The chunk is transmitted to all input streams that are connected to the
   output. The mechanism used to transmit data depends on the ``protocol`` and
   ``transfermode`` arguments used during 
   :func:`output stream configuration <OutputStream.configure>`:
   
   * Plain data stream over TCP: data is sent by TCP using a ZeroMQ socket.
   * Plain data stream within process: data is sent using a ZeroMQ "inproc" socket,
     which avoids uncecessary memory copies.
   * Shared memory: data is written into shared memory, and the new memory
     pointer is sent using a TCP or inproc ZeroMQ socket.
     
4. **Reassembly:** Each connected input stream independently receives data chunks and
   reassembles the stream.
5. **Post-filtering:** The reconstructed stream data is passed through another user-defined sequence
   of filtering functions before being made available to the stream user.

When transmitting plain data streams, Pyacq tries to maximize throughput by
avoiding any unnecessary data copies. In most cases, a copy is required only if
the input array does not occupy a contiguous block of memory.

.. seealso:: :func:`OutputStream.configure()` 

A Simple Example
----------------

In this example, we pass an array from one thread to another::
    
    import numpy as np
    import pyacq
    import threading

    data = np.array([[1,2], [3,4], [5,6]])

    # Create and configure the output stream (sender)
    out = pyacq.OutputStream()
    out.configure(dtype=data.dtype)

    # Create the input stream (receiver) and connect it to
    # the output stream
    inp = pyacq.InputStream()
    inp.connect(out)

    # Start a background thread that just receives and prints
    # data from the input stream
    def receiver():
        global inp
        while True:
            d = inp.recv()
            print("Received: %s" % repr(d))

    thread = threading.Thread(target=receiver, daemon=True)
    thread.start()

    # Send data through the stream
    out.send(data)


If we run this code from an interactive shell, the last few lines might look
like::
    
    >>> out.send(data)
    >>> Received: (6, array([[1, 2],
           [3, 4],
           [5, 6]]))

At this point, we may continue calling ``out.send()`` indefinitely. 

Notes:
    
    * In this example, data is sent over the stream using the default method:
      each chunk is serialized and transmitted over a tcp socket. This default
      works well when sending data between processes; for threads,
      however, we can achieve much better performance with other methods.
      (see :func:`OutputStream.configure()`)
    * InputStream and OutputStream are not thread-safe. Once the input thread 
      is started, we should not attempt to access the InputStream's attributes
      or methods from the main thread. Likewise, we should not attempt to call
      ip.connect(out) from within the input thread.
    * In this example we have not provided any way to ask the stream thread to
      exit. Setting ``daemon=True`` when creating the thread ensures that, once
      the main thread exits, the stream thread will not prevent the process
      from exiting as well.


Streaming between processes
---------------------------

In the example above, we used ``inp.connect(out)`` to establish the connection
between the ends of the stream. How does this work when we have the input and
output in different processes, or on different machines? We use pyacq's RPC
system to allow the streams to negotiate a connection, exactly as if they
had been created in the same process::

    import pyacq
    
    # Start a local RPC server so that a remote InputStream will be able
    # to make configuration requests from a local OutputStream:
    s = pyacq.RPCServer()
    s.run_lazy()

    # Create the output stream in the local process
    o = pyacq.OutputStream()
    o.configure(dtype=float)

    # Spawn a new process and create an InputStream there
    p = pyacq.ProcessSpawner()
    rpyacq = p.client._import('pyacq')
    i = rpyacq.InputStream()
    
    # Connect the streams exactly as if they were local
    i.connect(o)

Although this example is somewhat contrived, it demonstrates the general
approach: assuming both processes are running an RPC server, one will be
able to initiate a stream connection as long as it has an RPC proxy to the
stream from the other process.


Using Streams in Custom Node Types
----------------------------------

:class:`Node` classes are responsible for handling most of the configuration for their
input/output streams as well as for sending, receiving, and reconstructing data
through the streams. This functionality is mostly hidden from Node users;
however, if you plan to write custom Node classes, then it is
necessary to understand this process in more detail.

Node subclasses may declare any required properties for their input and output
streams through the ``_input_specs`` and ``_output_specs`` class attributes.
Each attribute is a dict whose keys are the names of the streams and whose
values provide the default configuration arguments for the stream. For example::
    
    class MyFilterNode(Node):
        _input_specs = {
            'analog_in': dict(streamtype='analogsignal', dtype='int16', shape=(-1, 2),
                              compression='', timeaxis=0, sample_rate=50000.),
            'trigger_in': dict(streamtype='digitalsignal', dtype='uint32', shape=(-1),
                               compression='', timeaxis=0, sample_rate=200000.),
        }

        _output_specs = {
            'filtered_out': dict(streamtype='analogsignal', dtype='float32', shape=(-1, 2),
                                 compression='', timeaxis=0, sample_rate=50000)}

This :class:`Node` subclass declares two input streams and one output stream:
an analog input called "analog_in", a digital input called "trigger_in", and
an analog output called "filtered_out". The configuration parameters specified
for each stream are passed to the ``spec`` argument of 
:func:`InputStream.__init__` or :func:`OutputStream.__init__`.

When the user calls :func:`Node.configure() <pyacq.core.Node.configure()>`,
the Node will have its last opportunity to create extra streams (if any) and apply
all configuration options to its streams.

Nodes call :func:`OutputStream.send()` to send new data via their output streams,
and :func:`InputStream.recv()` to receive data from their input streams. If the
stream is a plaindata type, then calling :func:`recv() <InputStream.recv()>` 
will return the next data chunk. In contrast, sharedmem streams only return the
poisition within the shared memory array of the next data chunk. In this case,
it may be more useful to call :func:`InputStream.get_array_slice()` to return
part of the shared memory buffer.

.. seealso::
    * The :ref:`Noise generator <noise_generator_example>` example demonstrates
      a simple node with an output stream. 
    * The :ref:`Stream monitor <simple_input_node_example>` example demonstrates
      a simple node with an input stream.


Using streams in GUI nodes
--------------------------

User interface nodes pose a unique challenge because they must somehow work
with the Qt event loop. Using a ``QTimer`` to poll an input node is a valid
option, but this requires a tradeoff between latency and CPU usage--a node that
responds quickly to stream input would have to poll with a short timer interval,
which can be computationally expensive.

A better alternative is to have a background thread block while receiving data
on the input stream, and then send a signal to the GUI event loop whenever it
receives a packet. This is the purpose of :class:`pyacq.core.ThreadPollInput`.

For example::
    
    instream = InputStream()
    instream.connect(outstream)
    
    poller = ThreadPollInput(input_stream=instream, return_data=True)
    
    def callback(position, data):
        print("Received new data packet at position %d" % position)
        
    poller.new_data.connect(callback)
    
In this example, we assume a Qt event loop is already running.
The :class:`pyacq.core.ThreadPollInput` instance starts a
background thread to receive data from ``instream``. When data is received,
a signal is emitted and the callback is invoked by the Qt event loop. Because
this stream is being accessed by another thread, it must **not** be accessed
from the main GUI thread until ``poller.stop()`` and ``poller.wait()`` have
been called.

The default behavior for :class:`pyacq.core.ThreadPollInput` is to emit a signal
whenever it receives a data packet. However, this behavior can be customized by
overriding the :func:pyacq.core.ThreadPollInput.processData` method in a subclass.


Stream management tools
-----------------------

Pyacq provides two simple tools for managing data as it moves between streams:
    
:class:`pyacq.core.StreamConverter` receives data from an output stream and
immediately sends it through another output stream, which could have a
different configuration. As an example, one could receive data from a sharedmem
stream and then use a :class:`pyacq.core.StreamConverter` to forward the data
over a tcp socket::
    
    conv = StreamConverter()
    conv.configure()
    
    # data arrives via outstream
    conv.input.connect(outstream)
    
    # ..and is forwarded via conv.output
    conv.output.configure(protocol='tcp')
    conv.initialize()
    
    # now we may connect another InputStream to conv.output

:class:`pyacq.core.ChannelSplitter` takes a multi-channel stream as input and
forwards data from individual channels (or groups of channels) via multiple
outputs. This is used primarily when streaming multichannel data to a cluster
of nodes that will preform a parallel computation. Although it would be possible
to simply send all channel data to all nodes, this could incur a performance
penalty depending on the stream protocol. By splitting the stream before sending
it to the compute nodes, we can avoid this extra overhead.


