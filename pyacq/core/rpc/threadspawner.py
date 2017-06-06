# -*- coding: utf-8 -*-
# Copyright (c) 2016, French National Center for Scientific Research (CNRS)
# Distributed under the (new) BSD License. See LICENSE for more info.
import threading
import logging
import atexit

from .client import RPCClient
from .server import RPCServer
from .log import get_logger_address, set_thread_name

logger = logging.getLogger(__name__)


class ThreadSpawner(object):
    """Utility for spawning and bootstrapping a new thread with an :class:`RPCServer`.
    
    Automatically creates an :class:`RPCClient` that is connected to the remote 
    thread (``spawner.client``).
    
    Parameters
    ----------
    name : str | None
        Optional process name that will be assigned to all remote log records.
    address : str
        ZMQ socket address that the new thread's RPCServer will bind to.
        Default is ``'tcp://127.0.0.1:*'``.
        
        **Note:** binding RPCServer to a public IP address is a potential
        security hazard (see :class:`RPCServer`).
    log_addr : str
        Optional log server address to which the new thread will send its log
        records.
    log_level : int
        Optional initial log level to assign to the root logger in the new
        thread.
        
    Examples
    --------
    
    ::
    
        # start a new thread
        thread = ThreadSpawner()
        
        # ask the thread to do some work
        mod = thread._import('my.module')
        mod.do_work()
        
        # close the thread
        thread.close()
        thread.join()
    """
    def __init__(self, name=None, address="tcp://127.0.0.1:*", log_addr=None, 
                 log_level=None, daemon=True):
        assert isinstance(address, (str, bytes))
        assert name is None or isinstance(name, str)
        assert log_addr is None or isinstance(log_addr, (str, bytes)), "log_addr must be str or None; got %r" % log_addr
        if log_addr is None:
            log_addr = get_logger_address()
        assert log_level is None or isinstance(log_level, int)
        if log_level is None:
            log_level = logger.getEffectiveLevel()
        
        self.name = name
        self.address = None
        startup_ev = threading.Event()
        args = (address, startup_ev)
        self.thread = threading.Thread(target=self.thread_run, args=args, name=name, daemon=daemon)
        self.thread.start()
        if startup_ev.wait(5) is False:
            raise TimeoutError("Timed out waiting for spawned thread.")
            
        logger.info("Spawned thread: %s", self.thread.name)
        
        self.client = RPCClient(self.address)
        
        # Automatically shut down thread when we exit. 
        atexit.register(self.stop)
        
    def join(self, timeout=10):
        """Wait for the thread to exit.
        """
        return self.thread.join(timeout)

    def stop(self):
        """Stop the thread by asking its RPC server to close.
        """
        if self.thread.is_alive() is False:
            return
        logger.info("Close thread: %s", self.thread.name)
        closed = self.client.close_server()
        assert closed is True, "Server refused to close. (reply: %s)" % closed

        self.join()

    def thread_run(self, address, event):
        self.server = RPCServer(address)
        self.address = self.server.address
        set_thread_name(self.name)
        event.set()
        self.server.run_forever()