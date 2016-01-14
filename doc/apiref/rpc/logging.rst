.. currentmodule:: pyacq.core.rpc.log

.. _apiref_rpc_logging:

Logging tools
=============

These tools allow log records and unhandled exceptions to be forwarded to a 
central log server. Basic usage consists of:
    
1. Start a log server in any process using :func:`start_log_server`. 
2. Attach a handler to the root logger (see Python logging documentation). If
   the log server is running in a process that can output to a terminal, then
   :class:`RPCLogHandler` can be used to display log records color-coded by
   source.
3. Set the log level of the root logger. Using INFO or DEBUG levels will reveal
   details about RPC communications between processes.
4. In the remote process set the log level and call :func:`set_host_name`, :func:`set_process_name`,
   :func:`set_thread_name`, and :func:`set_logger_address` (note that 
   :class:`ProcessSpawner <pyacq.core.rpc.ProcessSpawner>` handles this step automatically).

.. autofunction:: start_log_server

.. autoclass::  LogServer
   :members:

.. autoclass::  LogSender
   :members:

.. autoclass::  RPCLogHandler

.. autofunction:: log_exceptions

.. autofunction:: set_host_name

.. autofunction:: get_host_name

.. autofunction:: set_process_name

.. autofunction:: get_process_name

.. autofunction:: set_thread_name

.. autofunction:: get_thread_name

.. autofunction:: set_logger_address

.. autofunction:: get_logger_address

