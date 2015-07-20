
import sys
import subprocess

from .rpc import RPCClient

class ProcessSpawner:
    def __init__(self, rpcserverclass, name, addr, **kargs):
        self.name = name
        self.addr = addr
        executable = sys.executable
        bootstrap = 'from pyacq import {0}; server={0}(name = {1}, addr = {2}'.format(rpcserverclass.__name__,repr(name), repr(addr) )
        bootstrap += ','.join( '{} = {}'.format(k, repr(v)) for k, v in kargs.items())
        bootstrap += '); server.run_forever();'
        self.proc = subprocess.Popen((executable, '-c', bootstrap), stdout = sys.stdout, stderr = sys.stderr)

    def wait(self):
        self.proc.wait()

    def kill(self):
        self.proc.kill()
        self.proc.wait()

    def stop(self):
        client = RPCClient(self.name, self.addr)
        client.close()
        self.proc.wait()

