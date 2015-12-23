Interacting with nodes
======================

Pyacq delegates its data handling tasks to objects called Nodes. Each type of 
Node implements a different part of the pipeline such as acquiring data from a
device, filtering or online analysis, visualization, or data storage. Nodes are
connected by Streams to form a graph in which data flows from device to screen
or to disk.


Creating nodes
--------------

In the simplest case, nodes may be created directly by instantiating their
classes::
    
    audio = pyacq.devices.PyAudio()
    viewer = pyacq.viewers.QOscilloscope()
    
For cases that require multiple processes or that are distributed
across machines, Pyacq provides mechanisms for creating and managing Nodes
remotely::

    manager = pyacq.create_manager()
    nodegroup = manager.default_nodegroup
    audio = nodegroup.create_node('PyAudio')
    viewer = nodegroup.create_node('QOscilloscope')
    
It is also possible to use both locally- and remotely-instantiated
Nodes in the same application. See :ref:`managing_distributed_nodes` for more
information about managing remote Nodes and their processes.
    

Configuring and connecting nodes
--------------------------------

Nodes are configured and connected in a few steps that must be executed in order:

1. Call ``node.configure(...)`` to set global parameters for the node such as 
   sample rate, channel selections, etc. Each Node class defines and documents the
   parameters accepted by its configure method.
2. Configure the node's output streams (if any) by calling
   ``node.outputs['output_name'].configure(...)``. This determines the method of
   communication that the stream will use--plain TCP data stream, shared memory,
   etc.--and any associated options such as compression and chunk size.
3. Connect inputs to their sources (if any) by calling 
   ``node.inputs['input_name'].connect(other_node.outputs['output_name'])``. The
   input will be automatically configured to match its associated output.
4. Call ``node.initialize()``, which will verify input/output settings, 
   allocate memory, prepare devices, etc.

The following code example, taken from ``examples/pyaudio_oscope.py``, demonstrates
the creation and configuration of two nodes: the first uses PyAudio to stream
an audio signal from a microphone, and the second displays the streamed data.

::

    # Create and configure audio input node
    dev = PyAudio()
    dev.configure(nb_channel=1, sample_rate=44100., input_device_index=default_input,
                  format='int16', chunksize=1024)
    dev.output.configure(protocol='tcp', interface='127.0.0.1', transfertmode='plaindata')
    dev.initialize()

    # Create an oscilloscope to display data.
    viewer = QOscilloscope()
    viewer.configure(with_user_dialog = True)

    # Connect audio stream to oscilloscope
    viewer.input.connect(dev.output)
    viewer.initialize()


Starting and stopping
---------------------

After a node is created, configured, and initialized, it is ready to begin 
acquiring or processing data. Calling ``node.start()`` instructs the node to
immediately begin reading data from its inputs and/or sending data through its
outputs. Calling ``node.stop()`` will stop all processing until ``start()`` is
called again::
    
    dev.start()
    viewer.start()
    
    ...
    
    dev.stop()
    viewer.stop()

To permanently deallocate any memory and device resources used by a node, call
``node.close()``. Nodes may be started and stopped multiple times, but may
not be reinitialized once they are closed.


Interacting with remote nodes
-----------------------------

It is often useful or necessary to have nodes distributed across multiple
threads, processes, or machines (see :ref:`managing_distributed_nodes`). Pyacq
uses a remote procedure call (RPC) system with object proxies to allow 
remotely-hosted nodes to be treated almost exactly like local nodes::
    
    # local:
    local_node = MyNodeType()
    local_node.configure(...)
    
    # remote:
    remote_node = nodegroup.create_node('MyNodeType')
    remote_node.configure(...)
    remote_node.output.configure(...)
    
    local_node.input.connect(remote_node.output)
    local_node.initialize()
    remote_node.initialize()

    local_node.start()
    remote_node.start()
    
In this example, calling any method on ``remote_node`` causes a message to be
sent to the process that owns the node, asking it to invoke the method on our
behalf. The calling process blocks until the return value is sent back. Similarly,
any attributes accessed from ``remote_node`` (such as ``remote_node.output``)
are automatically returned as proxies to the remote process.

One major difference between local and proxied objects is that remote methods
may be invoked asynchronously. This done by adding the special keyword argument
``_sync='async'`` to the method call, which causes the call to immediately return
a `Future` object (see 
`concurrent.Future <https://docs.python.org/3/library/concurrent.futures.html#future-objects>`_
in the Python library reference) that may be used to check the status of the request::
    
    future = remote_node.configure(..., _sync='async')
    
    while not future.done():
        # do something while we wait for response
        
    # get the result of calling configure()
    result = future.result()

More information about the RPC system can be found in the
:ref:`API reference <apiref_rpc>`.
