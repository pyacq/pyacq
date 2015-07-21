import sys
import subprocess
import atexit
import logging
import zmq

from .rpc import RPCClient


bootstrap_template = """
import zmq
import time
import logging
import pyacq

logging.getLogger().level={loglevel}

try:
    # Create server
    logging.info("Start `{class_name}({args})`")
    from pyacq import {class_name}
    server = {class_name}({args})
except:
    print("Error starting process with `{class_name}({args})`:")
    raise
    
# Report server status to spawner
status = {{'addr': server._addr.decode()}}
bootstrap_sock = zmq.Context.instance().socket(zmq.PAIR)
bootstrap_sock.connect({bootstrap_addr})
while True:
    # send status repeatedly until spawner gives a reply.
    bootstrap_sock.send_json(status)
    try:
        bootstrap_sock.recv(zmq.NOBLOCK)
    except zmq.error.Again:
        time.sleep(0.01)
        continue
    break

# Run server until heat death of universe
server.run_forever()
"""


class ProcessSpawner:
    def __init__(self, rpcserverclass, name, addr, **kargs):
        self.name = name
        
        # temporary socket to allow the remote process to report its status.
        bootstrap_addr = 'tcp://127.0.0.1:*'
        bootstrap_sock = zmq.Context.instance().socket(zmq.PAIR)
        bootstrap_sock.bind(bootstrap_addr)
        bootstrap_addr = bootstrap_sock.getsockopt(zmq.LAST_ENDPOINT)
        
        # Spawn new process
        class_name = rpcserverclass.__name__
        kargs.update({'name': name, 'addr': addr})
        args = ', '.join('{}={}'.format(k, repr(v)) for k, v in kargs.items())
        loglevel = str(logging.getLogger().getEffectiveLevel())
        bootstrap = bootstrap_template.format(class_name=class_name, args=args,
                                              bootstrap_addr=bootstrap_addr,
                                              loglevel=loglevel)
        executable = sys.executable
        self.proc = subprocess.Popen((executable, '-c', bootstrap))
        logging.info("Spawned process: %d", self.proc.pid)
        
        # Automatically shut down process when we exit. 
        atexit.register(self.kill)
        
        # Receive status information (especially the final RPC address)
        self._status = bootstrap_sock.recv_json()
        logging.info("recv status %s", self._status)
        bootstrap_sock.send(b'OK')
        self.addr = self._status['addr']
        
        self.client = RPCClient(name, self.addr)
        assert self.client.ping() == 'pong', "Failed to connect to RPC server."
        
    def wait(self):
        self.proc.wait()

    def kill(self):
        if self.proc.poll() is not None:
            return
        logging.info("Kill process: %d", self.proc.pid)
        self.proc.kill()
        self.proc.wait()

    def stop(self):
        if self.proc.poll() is not None:
            return
        logging.info("Close process: %d", self.proc.pid)
        self.client.close()
        self.proc.wait()

