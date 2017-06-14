# -*- coding: utf-8 -*-
# Copyright (c) 2016, French National Center for Scientific Research (CNRS)
# Distributed under the (new) BSD License. See LICENSE for more info.

import sys
import os
import json
import subprocess
import atexit
import zmq
import logging
import threading
import time
from pyqtgraph.Qt import QtCore

from .client import RPCClient
from .log import get_logger_address, LogSender


logger = logging.getLogger(__name__)


class ProcessSpawner(object):
    """Utility for spawning and bootstrapping a new process with an :class:`RPCServer`.
    
    Automatically creates an :class:`RPCClient` that is connected to the remote 
    process (``spawner.client``).
    
    Parameters
    ----------
    name : str | None
        Optional process name that will be assigned to all remote log records.
    address : str
        ZMQ socket address that the new process's RPCServer will bind to.
        Default is ``'tcp://127.0.0.1:*'``.
        
        **Note:** binding RPCServer to a public IP address is a potential
        security hazard (see :class:`RPCServer`).
    qt : bool
        If True, then start a Qt application in the remote process, and use
        a :class:`QtRPCServer`.
    log_addr : str
        Optional log server address to which the new process will send its log
        records. This will also cause the new process's stdout and stderr to be
        captured and forwarded as log records.
    log_level : int
        Optional initial log level to assign to the root logger in the new
        process.
    executable : str | None
        Optional python executable to invoke. The default value is `sys.executable`.
    log_output : bool
        If True, then the child process stdout and stderr are captured and 
        forwarded to the log server.
        
    Examples
    --------
    
    ::
    
        # start a new process
        proc = ProcessSpawner()
        
        # ask the child process to do some work
        mod = proc._import('my.module')
        mod.do_work()
        
        # close the child process
        proc.close()
        proc.wait()
    """
    def __init__(self, name=None, address="tcp://127.0.0.1:*", qt=False, log_addr=None, 
                 log_level=None, executable=None, log_output=True):
        #logger.warn("Spawning process: %s %s %s", name, log_addr, log_level)
        assert qt in (True, False)
        assert isinstance(address, (str, bytes))
        assert name is None or isinstance(name, str)
        assert log_addr is None or isinstance(log_addr, (str, bytes)), "log_addr must be str or None; got %r" % log_addr
        if log_addr is None:
            log_addr = get_logger_address()
        assert log_level is None or isinstance(log_level, int)
        if log_level is None:
            log_level = logger.getEffectiveLevel()
        
        self.qt = qt
        self.name = name
        
        # temporary socket to allow the remote process to report its status.
        bootstrap_addr = 'tcp://127.0.0.1:*'
        bootstrap_sock = zmq.Context.instance().socket(zmq.PAIR)
        bootstrap_sock.setsockopt(zmq.RCVTIMEO, 10000)
        bootstrap_sock.bind(bootstrap_addr)
        bootstrap_sock.linger = 1000 # don't let socket deadlock when exiting
        bootstrap_addr = bootstrap_sock.last_endpoint
        
        # Spawn new process
        class_name = 'QtRPCServer' if qt else 'RPCServer'
        args = {'address': address}
        bootstrap_conf = dict(
            class_name=class_name, 
            args=args,
            bootstrap_addr=bootstrap_addr.decode(),
            loglevel=log_level,
            logaddr=log_addr.decode() if log_addr is not None else None,
            qt=qt,
        )
        
        if executable is None:
            executable = sys.executable

        cmd = (executable, '-m', 'pyacq.core.rpc.bootstrap')
        if name is not None:
            cmd = cmd + (name,)

        if log_output is True and log_addr is not None:
            # start process with stdout/stderr piped
            self.proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=subprocess.PIPE,
                                         stdout=subprocess.PIPE)
            
            self.proc.stdin.write(json.dumps(bootstrap_conf).encode())
            self.proc.stdin.close()
            
            # create a logger for handling stdout/stderr and forwarding to log server
            self.logger = logging.getLogger(__name__ + '.' + str(id(self)))
            self.logger.propagate = False
            self.log_handler = LogSender(log_addr, self.logger)
            if log_level is not None:
                self.logger.level = log_level
            
            # create threads to poll stdout/stderr and generate / send log records
            self.stdout_poller = PipePoller(self.proc.stdout, self.logger.info, '[%s.stdout] '%name)
            self.stderr_poller = PipePoller(self.proc.stderr, self.logger.warn, '[%s.stderr] '%name)
            
        else:
            # don't intercept stdout/stderr
            self.proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
            self.proc.stdin.write(json.dumps(bootstrap_conf).encode())
            self.proc.stdin.close()
            
        logger.info("Spawned process: %d", self.proc.pid)
        
        # Receive status information (especially the final RPC address)
        try:
            status = bootstrap_sock.recv_json()
        except zmq.error.Again:
            raise TimeoutError("Timed out waiting for response from spawned process.")
        logger.debug("recv status %s", status)
        bootstrap_sock.send(b'OK')
        bootstrap_sock.close()
        
        if 'address' in status:
            self.address = status['address']
            #: An RPCClient instance that is connected to the RPCServer in the remote process
            self.client = RPCClient(self.address.encode())
        else:
            err = ''.join(status['error'])
            self.kill()
            raise RuntimeError("Error while spawning process:\n%s" % err)
        
        # Automatically shut down process when we exit. 
        atexit.register(self.stop)
        
    def wait(self, timeout=10):
        """Wait for the process to exit and return its return code.
        """
        # Using proc.wait() can deadlock; use communicate() instead.
        # see: https://docs.python.org/2/library/subprocess.html#subprocess.Popen.wait
        try:
            
            self.proc.communicate()
        except (AttributeError, ValueError):
            # Python bug: http://bugs.python.org/issue30203
            # Calling communicate on process with closed i/o can generate
            # exceptions.
            pass
        
        start = time.time()
        sleep = 1e-3
        while True:
            rcode = self.proc.poll()
            if rcode is not None:
                return rcode
            if time.time() - start > timeout:
                raise TimeoutError("Timed out waiting on process exit for %s" % self.name)
            time.sleep(sleep)
            sleep = min(sleep*2, 100e-3)

    def kill(self):
        """Kill the spawned process immediately.
        """
        if self.proc.poll() is not None:
            return
        logger.info("Kill process: %d", self.proc.pid)
        self.proc.kill()

        self.wait()

    def stop(self):
        """Stop the spawned process by asking its RPC server to close.
        """
        if self.proc.poll() is not None:
            return
        logger.info("Close process: %d", self.proc.pid)
        closed = self.client.close_server()
        assert closed is True, "Server refused to close. (reply: %s)" % closed

        self.wait()

    def poll(self):
        """Return the spawned process's return code, or None if it has not
        exited yet.
        """
        return self.proc.poll()


class PipePoller(threading.Thread):
    
    def __init__(self, pipe, callback, prefix):
        threading.Thread.__init__(self, daemon=True)
        self.pipe = pipe
        self.callback = callback
        self.prefix = prefix
        self.start()
        
    def run(self):
        callback = self.callback
        prefix = self.prefix
        pipe = self.pipe
        while True:
            line = pipe.readline().decode()
            if line == '':
                break
            callback(prefix + line[:-1])
