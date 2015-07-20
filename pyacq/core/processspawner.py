
import sys
import subprocess

from .rpc import RPCClientSocket


bootstrap_template = """
from pyacq import {class_name} 
server = {class_name}({args})
server.run_forever()
"""


class ProcessSpawner:
    def __init__(self, rpcserverclass, **kargs):
        self.rpc_name = name
        self.rpc_address = addr
        class_name = rpcserverclass.__name__
        args = ','.join('{}={}'.format(k, repr(v)) for k, v in kargs.items())
        bootstrap = bootstrap_template.format(class_name=class_name, args=args)
        executable = sys.executable
        self.proc = subprocess.Popen((executable, '-c', bootstrap))

    def wait(self):
        self.proc.wait()

    def kill(self):
        self.proc.kill()
        self.proc.wait()

    def stop(self):
        #TODO send a message to server
        sock = RPCClientSocket()
        client = sock.get_client('some_server')
        
        self.proc.wait()




if __name__ == '__main__':
    import time
    
    class MyServer(RPCServer):
        def method1(self):
            return
    
    p1 = ProcessSpawer(MyServer, 'server1','tcp://localhost:5000')
    p2 = ProcessSpawer(MyServer, 'server1','tcp://localhost:5001')
    p3 = ProcessSpawer(MyServer, 'server1','tcp://localhost:5002')

    time.sleep(2.)
    p1.wait()
    p2.wait()
    p3.wait()
