.. _managing_distributed_nodes:

Managing distributed nodes
==========================

In Pyacq it is often useful to have nodes distributed across multiple threads,
processes, or machines. Although it is straightforward to manually create and
communicate with other processes, it can become cumbersome as the number of
distributed resources increases. Pyacq provides high-level tools for managing
processes and the nodes hosted within them:

* ``Manager`` is a central point of control for connecting to remote hosts; 
  starting, stopping, and monitoring distributed processes; and collecting
  node connectivity information.
* ``Host`` is a server that runs on remote machines to allow Pyacq to connect and
  spawn new worker processes.
* ``NodeGroup`` is a simple object that manages multiple nodes within a single
  process.

The general procedure for running a set of distributed nodes looks like:
    
1. Run ``Host`` servers on each remote machine (these can be left running indefinitely).
2. Create a ``Manger`` from the main process.
3. Ask the ``Manager`` to connect to each ``Host`` server.
4. Create ``NodeGroups`` as needed. Each ``NodeGroup`` appears inside a newly spawned
   process on any of the available hosts.
5. Create ``Nodes`` as needed within each ``NodeGroup``.
6. Configure, start, and stop ``Nodes``.
7. Close the ``Manager``. This will shut down all ``NodeGroups`` across all hosts.

[figure]


Creating a manager
------------------

Each application should only start one manager at most by calling the
``create_manager()`` function::
    
    import pyacq
    manager = pyacq.create_manager()

By default, the manager is created in a new process and a proxy to the manager
is returned. This allows the manager to listen and respond in the background 
to requests made by the hosts, nodegroups, and nodes associated with the
application.

Calling ``create_manager()`` also starts a log server to which all error
messages will be sent. Any spawned processes that are associated with this
application will forward their log messages, uncaught exceptions, and
stdout/stderr output back to the log server. 

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
shown above. For each machine that runs a host server, we ask the manager to 
make contact with the host::
    
    host = manager.add_host('tcp://10.0.0.53:8000')
    
Making this conection ensures that 1) the manager is aware that it needs to
monitor its resources on the host, 2) the host will inform the manager if
any of its processes dies unexpectedly and 3) the host will forward all log
records, exceptions, and stdout/stderr output back to the manager's log server.



Creating nodes
--------------

The manager itself also creates a local Host that it uses to create nodegroups
on its own machine.

example

