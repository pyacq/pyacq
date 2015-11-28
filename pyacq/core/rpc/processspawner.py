import sys
import subprocess
import atexit
import zmq
import logging
import threading
from pyqtgraph.Qt import QtCore

from .client import RPCClient
from .log import get_logger_address, LogSender


logger = logging.getLogger(__name__)


bootstrap_template = """
import zmq
import time
import sys
import traceback
import faulthandler
import logging

faulthandler.enable()
logger = logging.getLogger()
logger.level = {loglevel}

from pyacq import {class_name}
from pyacq.core.rpc import log

if {qt}:
    import pyqtgraph as pg
    app = pg.mkQApp()
    app.setQuitOnLastWindowClosed(False)

if {procname} is not None:
    log.set_process_name({procname})
if {logaddr} is not None:
    log.set_logger_address({logaddr})

log.log_exceptions()

logger.info("New process {procname} {class_name}({args}) log_addr:{logaddr} log_level:{loglevel}")

bootstrap_sock = zmq.Context.instance().socket(zmq.PAIR)
bootstrap_sock.connect({bootstrap_addr})
bootstrap_sock.linger = 1000

# Create RPC server
try:
    # Create server
    server = {class_name}({args})
    status = {{'addr': server.address.decode()}}
except:
    logger.error("Error starting {class_name} with args: {args}:")
    status = {{'error': traceback.format_exception(*sys.exc_info())}}
    
# Report server status to spawner
start = time.time()
while time.time() < start + 10.0:
    # send status repeatedly until spawner gives a reply.
    bootstrap_sock.send_json(status)
    try:
        bootstrap_sock.recv(zmq.NOBLOCK)
        break
    except zmq.error.Again:
        time.sleep(0.01)
        continue

bootstrap_sock.close()

# Run server until heat death of universe
if 'addr' in status:
    server.run_forever()
    
if {qt}:
    app.exec_()
"""


class ProcessSpawner(object):
    """Utility for spawning and bootstrapping a new process with an RPC server.
    
    `ProcessSpawner.client` is an RPCClient that is connected to the remote
    server.
    
    Parameters
    ----------
    name : str | None
        Optional process name that will be assigned to all remote log records.
    addr : str
        ZMQ socket address that the new process's RPCServer will bind to.
        Default is 'tcp://*:*'.
    qt : bool
        If True, then start a Qt application in the remote process, and use
        a QtRPCServer.
    log_addr : str
        Optional log server address to which the new process will send its log
        records. This will also cause the new process's stdout and stderr to be
        captured and forwarded as log records.
    log_level : int
        Optional initial log level to assign to the root logger in the new
        process.
    executable : str | None
        Optional python executable to invoke. The default value is `sys.executable`.
    """
    def __init__(self, name=None, addr="tcp://*:*", qt=False, log_addr=None, 
                 log_level=None, executable=None):
        #logger.warn("Spawning process: %s %s %s", name, log_addr, log_level)
        assert qt in (True, False)
        assert isinstance(addr, (str, bytes))
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
        bootstrap_sock.linger = 1000
        bootstrap_addr = bootstrap_sock.getsockopt(zmq.LAST_ENDPOINT)
        
        # Spawn new process
        class_name = 'QtRPCServer' if qt else 'RPCServer'
        args = "addr='%s'" % addr
        bootstrap = bootstrap_template.format(class_name=class_name, args=args,
                                              bootstrap_addr=bootstrap_addr,
                                              loglevel=log_level, qt=str(qt),
                                              logaddr=log_addr, procname=repr(name))
        
        if executable is None:
            executable = sys.executable

        if log_addr is not None:
            # start process with stdout/stderr piped
            self.proc = subprocess.Popen((executable, '-c', bootstrap), 
                                         stderr=subprocess.PIPE, stdout=subprocess.PIPE)
            
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
            self.proc = subprocess.Popen((executable, '-c', bootstrap))
            
        logger.info("Spawned process: %d", self.proc.pid)
        
        # Receive status information (especially the final RPC address)
        try:
            status = bootstrap_sock.recv_json()
        except zmq.error.Again:
            raise TimeoutError("Timed out waiting for response from spawned process.")
        logger.debug("recv status %s", status)
        bootstrap_sock.send(b'OK')
        bootstrap_sock.close()
        
        if 'addr' in status:
            self.addr = status['addr']
            self.client = RPCClient(self.addr.encode())
        else:
            err = ''.join(status['error'])
            self.kill()
            raise RuntimeError("Error while spawning process:\n%s" % err)
        
        # Automatically shut down process when we exit. 
        atexit.register(self.stop)
        
    def wait(self):
        self.proc.wait()

    def kill(self):
        if self.proc.poll() is not None:
            return
        logger.info("Kill process: %d", self.proc.pid)
        self.proc.kill()
        self.proc.wait()

    def stop(self):
        if self.proc.poll() is not None:
            return
        logger.info("Close process: %d", self.proc.pid)
        closed = self.client.close_server()
        assert closed is True, "Server refused to close. (reply: %s)" % closed
        self.proc.wait()


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
            line = pipe.readline().decode()[:-1]
            if line == '':
                break
            callback(prefix + line)
        
    

