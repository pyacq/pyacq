.. currentmodule:: pyacq.core.rpc

.. _apiref_rpc:


Remote Process Control
======================

Pyacq implements a system for spawning and controlling remote processes through
object proxies. This allows remote objects to be treated almost exactly as if 
they were local objects, with the exception that methods of object proxies may
be called asynchronously.

The remote process control system consists of several components:

* :class:`RPCServer` uses ZeroMQ to listen for serialized requests to control the process
  by invoking methods, returning objects, etc. RPCServer instances are automatically
  created in subprocesses when using ProcessSpawner.
* :class:`RPCClient` sends messages and receives responses from an RPCServer in another
  thread, process, or host. Each RPCClient instance connects to only one
  RPCServer. RPCClient instances are created automatically when using
  ProcessSpawner, or can be created manually using RPCClient.get_client.
* :class:`ObjectProxy` is the class used to represent any type of remote object. Invoking
  methods on an ObjectProxy causes a request to be sent to the remote process,
  and the result is eventually returned via the ObjectProxy.
* :class:`ProcessSpawner` is used to spawn new processes on the same machine as the caller.
  New processes will automatically start an RPCServer, and an RPCClient will
  be created in the parent process.
* :ref:`Serializers <apiref_rpc_serializers>` (currently msgpack and json are supported) are used to encode basic
  python types for transfer over ZeroMQ sockets. Clients are free to pick
  whichever serializer they prefer. List of data types:
* :ref:`Logging tools <apiref_rpc_logging>` that allow log records, uncaught excaptions, and stdout/stderr
  data to be sent to a remote log server. This is essential for debugging
  multiprocess applications.

The following simple example makes use of most of these components, although 
only ProcessSpawner and ObjectProxy are directly visible to the user::

    from pyacq.core.rpc import ProcessSpawner
    
    # Start a new process with an RPCServer running inside
    proc = ProcessSpawner()
    
    # Ask the remote process to import a module and return a proxy to it
    remote_col = proc.client._import('collections')
    
    # Create a new object (an ordered dict) in the remote process
    remote_dict = remote_col.OrderedDict()
    
    # Interact with the new object exactly as if it were local:
    remote_dict['x'] = 1
    assert 'x' in remote_dict.keys()
    assert remote_dict['x'] == 1
    
Using object proxies allows remote objects to be accessed using the same syntax
as if they were local. However, there are two major differences to consider when
using remote objects:

First, function arguments and return values in Python are passed by reference.
This means that both the caller and the callee operate on the *same* Python
object. Since it is not possible to share python objects between processes, 
we are restricted to sending them either by copy or by proxy. By default,
arguments and return values for remote functions are serialized if possible, or
passed by proxy otherwise.

Second, remote functions can be called asynchronously. By default, calling
a remote function will block until the return value has arrived. However, any
remote function call can be made asynchronous by adding a special argument:
``_sync='async'``. In this case, the function call will immediately return a
:class:`Future` object that can be used to
access the return value when it arrives.



RPC Classes
-----------

.. autoclass::  pyacq.core.rpc.RPCClient
   :members:

.. autoclass::  pyacq.core.rpc.RPCServer
   :members:

.. autoclass::  pyacq.core.rpc.ObjectProxy
   :members: _set_proxy_options, _get_value, __getattr__, __setattr__, __call__, __getitem__, __setitem__, _delete 

.. autoclass::  pyacq.core.rpc.ProcessSpawner
   :members:

.. autoclass:: pyacq.core.rpc.Future
   :members:


.. _apiref_rpc_serializers:

Serializers
-----------

- which are available
- serializable data types
    tuple/list
    bytes/ndarray efficiency
- adding new serializers


.. _apiref_rpc_logging:

Logging tools
-------------

.. autofunction:: pyacq.core.rpc.log.start_log_server

.. autoclass::  pyacq.core.rpc.log.LogServer
   :members:

.. autoclass::  pyacq.core.rpc.log.LogSender
   :members:

.. autofunction:: pyacq.core.rpc.log.set_host_name

.. autofunction:: pyacq.core.rpc.log.get_host_name

.. autofunction:: pyacq.core.rpc.log.set_process_name

.. autofunction:: pyacq.core.rpc.log.get_process_name

.. autofunction:: pyacq.core.rpc.log.set_thread_name

.. autofunction:: pyacq.core.rpc.log.get_thread_name

.. autofunction:: pyacq.core.rpc.log.set_logger_address

.. autofunction:: pyacq.core.rpc.log.get_logger_address

