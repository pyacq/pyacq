.. currentmodule:: pyacq.core

.. _managing_distributed_nodes:

Managing distributed nodes
==========================

In Pyacq it is often useful to have nodes distributed across multiple threads,
processes, or machines. Although it is straightforward to manually create and
communicate with other processes, it can become cumbersome as the number of
distributed resources increases. Pyacq provides high-level tools for managing
processes and the nodes hosted within them:

* :class:`Manager` is a central point of control for connecting to remote hosts; 
  starting, stopping, and monitoring distributed processes; and collecting
  node connectivity information.
* :class:`Host <pyacq.core.host.Host>` is a server that runs on remote machines to allow Pyacq to connect and
  spawn new worker processes.
* :class:`NodeGroup` is a simple object that manages multiple nodes within a single
  process.

The general procedure for running a set of distributed nodes looks like:
    
1. Run Host servers on each remote machine (these can be left running indefinitely).
2. Create a Manger from the main process.
3. Ask the Manager to connect to each Host server.
4. Create NodeGroups as needed. Each NodeGroup appears inside a newly spawned
   process on any of the available hosts.
5. Create Nodes as needed within each NodeGroup.
6. Configure, start, and stop Nodes.
7. Close the Manager. This will shut down all NodeGroups across all hosts.


Creating a manager
------------------

Each application should only start one Manager at most by calling the
:func:`create_manager` function::
    
    import pyacq
    manager = pyacq.create_manager()

By default, the Manager is created in a new process and a :class:`proxy <rpc.ObjectProxy>`
to the Manager
is returned. This allows the Manager to listen and respond in the background 
to requests made by the Hosts, NodeGroups, and Nodes associated with the
application.

Calling :func:`create_manager` also starts a :ref:`log server <apiref_rpc_logging>`
to which all error messages will be sent. Any spawned processes that are
associated with this application will forward their log messages, uncaught
exceptions, and stdout/stderr output back to the log server. 

The log server runs inside a new thread of the main process. By default, it
prints each received log record along with information about the
source host, process, and thread that generated the record. All log records
are sorted by their timestamps before being displayed, so it is important that
the system clocks are precisely synchronized.


Connecting to remote hosts
--------------------------

In order to connect to another machine on the network, the remote machine must
be running a server that allows the manager to start and stop new processes.
This can be done by running the host server script provided with Pyacq::
    
    $ python tools/host_server.py tcp://10.0.0.53:8000

The IP address and port on which the server should run must be provided as
shown above. For each machine that runs a host server, we ask the Manager to 
make contact with the Host::
    
    host = manager.add_host('tcp://10.0.0.53:8000')
    
Making this conection ensures that 1) the Manager is aware that it needs to
monitor its resources on the host, 2) the Host will inform the Manager if
any of its processes dies unexpectedly and 3) the Host will forward all log
records, exceptions, and stdout/stderr output back to the Manager's log server.



Creating remote Nodes
---------------------

Although there are few differences between interacting with remote versus local
Nodes, a little more effort is required to create a Node on a remote host. We
will start by creating a new process on the remote host using
:func:`Manager.create_nodegroup`, then create a new Node using
:func:`NodeGroup.create_node`::
    
    # Create a new process with a NodeGroup on the remote host    
    nodegroup = manager.create_nodegroup(host)
    
    # Next, request the NodeGroup to create a new Node    
    node = nodegroup.create_node('PyAudio', **kwargs)
    
We now have a :class:`proxy <rpc.ObjectProxy>` to a :class:`Node` that has been created in the remote process.
We can use this proxy to configure, initialize, start, and stop the Node,
:ref:`exactly as we would with a locally instantiated Node <interacting_with_nodes>`::
    
    node.configure(...)
    node.initialize(...)
    node.start()
    node.stop()

Optionally, we can also request the NodeGroup to remove the Node (if we omit
this step, then the Manager will take care of it when it exits)::
    
    nodegroup.remove_node(node)


Registering new Node classes
----------------------------

Whereas local Nodes are instantiated directly from their classes, remote Nodes
are instantiated using their class *names*. Consequently, custom Node classes
must be registered through the remote NodeGroup using 
:func:`register_node_type_from_module() <NodeGroup.register_node_type_from_module>`::
    
    nodegroup.register_node_type_from_module('my.module.name', 'MyClassName')
    
This requests the remote NodeGroup to import the named module and to register
the named Node subclass found there. Following this call, it is possible to
create new instances of your custom Node class within the remote NodeGroup::
    
    my_node = nodegroup.create_node('MyClassName', ...)


.. seealso:: :func:`NodeGroup.register_node_type_from_module`