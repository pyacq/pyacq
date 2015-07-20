
import sys
import subprocess

from .rpc import RPCClient


bootstrap_template = """
try:
    print("Start `{class_name}({args})`")
    from pyacq import {class_name}
    server = {class_name}({args})
    server.run_forever()
    
except:
    print("Error starting process with `{class_name}({args})`:")
    raise
"""


class ProcessSpawner:
    def __init__(self, rpcserverclass, name, addr, **kargs):
        self.name = name
        self.addr = addr
        class_name = rpcserverclass.__name__
        kargs.update({'name': name, 'addr': addr})
        args = ', '.join('{}={}'.format(k, repr(v)) for k, v in kargs.items())
        bootstrap = bootstrap_template.format(class_name=class_name, args=args)
        executable = sys.executable
        self.proc = subprocess.Popen((executable, '-c', bootstrap))
        self.client = RPCClient(name, addr)
        assert self.client.ping() == 'pong', "Failed to start process."

    def wait(self):
        self.proc.wait()

    def kill(self):
        self.proc.kill()
        self.proc.wait()

    def stop(self):
        self.client.close()
        self.proc.wait()

