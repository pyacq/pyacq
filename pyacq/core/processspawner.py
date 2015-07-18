
import sys
import subprocess

from .rpc import RPCClientSocket

class ProcessSpawner:
    def __init__(self, rpcserverclass, name, addr, **kargs):
        executable = sys.executable
        bootstrap = 'from pyacq import {0}; server={0}(name = {1}, addr = {2}'.format(rpcserverclass.__name__,repr(name), repr(addr) )
        bootstrap += ','.join( '{} = {}'.format(k, repr(v)) for k, v in kargs.items())
        bootstrap += '); server.run_forever();'
        self.proc = subprocess.Popen((executable, '-c', bootstrap))#, stdout = sys.stdout, stderr = sys.stderr)

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
