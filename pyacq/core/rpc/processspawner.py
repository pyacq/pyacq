import sys
import subprocess
import atexit
import zmq

from .client import RPCClient
from ..log import logger

logger.level = 1

bootstrap_template = """
import zmq
import time
import sys
import traceback
import faulthandler
faulthandler.enable()

from pyacq import {class_name}
from pyacq.core.log import logger

if {qt}:
    import pyqtgraph as pg
    app = pg.mkQApp()
    app.setQuitOnLastWindowClosed(False)

logger.level = {loglevel}

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
    """
    def __init__(self, name, addr="tcp://*:*", qt=False):
        self.name = name
        self.qt = qt
        
        # temporary socket to allow the remote process to report its status.
        bootstrap_addr = 'tcp://127.0.0.1:*'
        bootstrap_sock = zmq.Context.instance().socket(zmq.PAIR)
        bootstrap_sock.bind(bootstrap_addr)
        bootstrap_addr = bootstrap_sock.getsockopt(zmq.LAST_ENDPOINT)
        
        # Spawn new process
        class_name = 'QtRPCServer' if qt else 'RPCServer'
        args = "name='%s', addr='%s'" % (name, addr)
        loglevel = str(logger.getEffectiveLevel())
        bootstrap = bootstrap_template.format(class_name=class_name, args=args,
                                              bootstrap_addr=bootstrap_addr,
                                              loglevel=loglevel, qt=str(qt))
        executable = sys.executable
        self.proc = subprocess.Popen((executable, '-c', bootstrap), 
                                     stdin=subprocess.PIPE, stdout=subprocess.PIPE)
        logger.info("Spawned process: %d", self.proc.pid)
        
        # Automatically shut down process when we exit. 
        atexit.register(self.kill)
        
        # Receive status information (especially the final RPC address)
        bootstrap_sock.setsockopt(zmq.RCVTIMEO, 1000)
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

