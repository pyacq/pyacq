import sys
import subprocess
import atexit
import zmq
import logging
from pyqtgraph.Qt import QtCore

from .client import RPCClient
from .log import get_logger_address


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

from pyacq import {class_name}
from pyacq.core.rpc import log

if {qt}:
    import pyqtgraph as pg
    app = pg.mkQApp()
    app.setQuitOnLastWindowClosed(False)

logger.level = {loglevel}
if {procname} is not None:
    log.set_process_name({procname})
if {logaddr} is not None:
    log.set_logger_address({logaddr})

bootstrap_sock = zmq.Context.instance().socket(zmq.PAIR)
bootstrap_sock.connect({bootstrap_addr})

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
    addr : str
        ZMQ socket address that the new process's RPCServer will bind to.
        Default is 'tcp://*:*'.
    qt : bool
        If True, then start a Qt application in the remote process, and use
        a QtRPCServer.
    logging : bool
        If True, then forward all log records from the remote process to 
        the locally used log server address (see rpc.log.get_logger_address).
    name : str | None
        Optional process name that will be assigned to all remote log records.
    """
    def __init__(self, addr="tcp://*:*", qt=False, logging=True, name=None):
        assert qt in (True, False)
        self.qt = qt
        
        # temporary socket to allow the remote process to report its status.
        bootstrap_addr = 'tcp://127.0.0.1:*'
        bootstrap_sock = zmq.Context.instance().socket(zmq.PAIR)
        bootstrap_sock.setsockopt(zmq.RCVTIMEO, 1000)
        bootstrap_sock.bind(bootstrap_addr)
        bootstrap_addr = bootstrap_sock.getsockopt(zmq.LAST_ENDPOINT)
        
        # Spawn new process
        class_name = 'QtRPCServer' if qt else 'RPCServer'
        args = "addr='%s'" % addr
        logaddr = repr(get_logger_address()) if logging else None
        loglevel = str(logger.getEffectiveLevel())
        bootstrap = bootstrap_template.format(class_name=class_name, args=args,
                                              bootstrap_addr=bootstrap_addr,
                                              loglevel=loglevel, qt=str(qt),
                                              logaddr=logaddr, procname=repr(name))
        executable = sys.executable
        self.proc = subprocess.Popen((executable, '-c', bootstrap),) 
                                     #stdin=subprocess.PIPE, stdout=subprocess.PIPE)
        #self.stdout_poller = PipePoller(self.proc.stdout)
        #self.stderr_poller = PipePoller(self.proc.stderr)
        logger.info("Spawned process: %d", self.proc.pid)
        
        # Automatically shut down process when we exit. 
        atexit.register(self.stop)
        
        # Receive status information (especially the final RPC address)
        status = bootstrap_sock.recv_json()
        logger.debug("recv status %s", status)
        bootstrap_sock.send(b'OK')
        if 'addr' in status:
            self.addr = status['addr']
            self.client = RPCClient(self.addr.encode())
        else:
            err = ''.join(status['error'])
            raise RuntimeError("Error while spawning process:\n%s" % err)
        
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
        if self.qt:
            self.client.quit_qapplication()
        else:
            self.client.close_server()
        self.proc.wait()


#class PipePoller(QtCore.QThread):
    
    #new_line = QtCore.Signal(object)
    
    #def __init__(self, pipe):
        #QThread.__init__(self)
        #self.pipe = pipe
        
    #def run(self):
        #while True:
            #line = self.pipe.readline()
            #if line == '':
                #break
            #self.new_line.emit(line)
        
    

