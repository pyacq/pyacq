"""
RPC implemented over zmq sockets.

- remote procedure calls can be synchronous, asynchronous, or no-return
- exceptions propagate nicely back to caller
- no specific event loop requirements


"""

import zmq
import random
import sys
import time
import weakref
import json
import concurrent.futures
import traceback


class RemoteCallException(Exception):
    def __init__(self, type_str, tb_str):
        self.type_str = type_str
        self.tb_str = tb_str
        
    def __str__(self):
        msg = '\n===> Remote exception was:\n' + ''.join(self.tb_str)
        return msg


class Future(concurrent.futures.Future):
    # todo: should we use concurrent.Future for this?
    def __init__(self, socket, call_id):
        concurrent.futures.Future.__init__(self)
        self.socket = socket
        self.call_id = call_id
    
    def cancel(self):
        return False

    def result(self, timeout=None):
        self.socket.process_until_future(self, timeout=timeout)
        return concurrent.futures.Future.result(self)


class RPCClientSocket(object):
    def __init__(self, addr='tcp://*:5152'):
        self.socket = zmq.Context.instance().socket(zmq.ROUTER)
        self.socket.bind(addr)
        self.clients = {}
        self.next_call_id = 0
        self.futures = weakref.WeakValueDictionary()
        
    def get_client(self, name):
        if name not in self.clients:
            self.clients[name] = RPCClient(name, self)
        return self.clients[name]
    
    def send(self, name, action, *args, **kwds):
        call_id = self.next_call_id
        self.next_call_id += 1
        cmd = {'action': action, 'call_id': call_id,
               'args': args, 'kwds': kwds}
        cmd = json.dumps(cmd).encode()
        #print("SEND:", name, cmd)
        self.socket.send_multipart([name, cmd])
        fut = Future(self, call_id)
        self.futures[call_id] = fut
        return fut

    def process(self):
        """Process all available incoming messages.
        """
        while True:
            try:
                ident = self.socket.recv(zmq.NOBLOCK)
                msg = self.socket.recv_json()
                self._process_msg(ident, msg)
            except zmq.error.Again:
                break  # no messages left

    def process_until_future(self, future, timeout=None):
        """Process all incoming messages until receiving a result for *future*. 
        """
        while not future.done():
            # wait patiently with blocking calls.
            # TODO: implement timeout
            ident = self.socket.recv()
            msg = self.socket.recv_json()
            self._process_msg(ident, msg)

    def _process_msg(self, ident, msg):
        if msg['action'] == 'return':
            fut = self.futures[msg['call_id']]
            if msg['error'] is not None:
                exc = RemoteCallException(*msg['error'])
                #print("GOT EXC:", exc)
                fut.set_exception(exc)
            else:
                fut.set_result(msg['rval'])
    

class RPCClient(object):
    def __init__(self, name, socket):
        self.name = name.encode()
        self.socket = socket
        
    def __getattr__(self, name):
        return self.get_method_proxy(name)
    
    def get_method_proxy(self, name):
        return RPCMethod(self, name)
    
    def call_method(self, method_name, *args, **kwds):
        return self.socket.send(self.name, 'call', method_name, *args, **kwds)

    
class RPCMethod(object):
    def __init__(self, client, method):
        self.client = client
        self.method = method
        
    def __call__(self, *args, **kwds):
        return self.client.call_method(self.method, *args, **kwds)



class RPCServer(object):
    def __init__(self, name, addr='tcp://localhost:5152'):
        self._name = name.encode()
        self._socket = zmq.Context.instance().socket(zmq.DEALER)
        self._socket.setsockopt(zmq.IDENTITY, self._name)
        self._socket.connect(addr)
        self._closed = False
        #print("START SERVER:", self._name)

    def _process_one(self):
        msg = self._socket.recv_json()
        if msg['action'] == 'call':
            try:
                method, args = msg['args'][0], msg['args'][1:]
                kwds = msg['kwds']
                call_id = msg['call_id']
                fn = getattr(self, method)
                if len(kwds) == 0:
                    # need to do this because some functions do not allow
                    # keyword arguments.
                    rval = fn(*args)
                else:
                    rval = fn(*args, **kwds)
                self._send_result(call_id, rval=rval)
            except:
                exc = sys.exc_info()
                exc_str = traceback.format_exception(*exc)
                self._send_result(call_id, error=(exc[0].__name__, exc_str))
        
    def _send_result(self, call_id, rval=None, error=None):
        #print("RESULT:", call_id, rval, error)
        self._socket.send_json({'action': 'return', 'call_id': call_id,
                                'rval': rval, 'error': error})

    def close(self):
        self._closed = True
        self.socket.close()

    def running(self):
        return not self._closed
    
    def run_forever(self):
        while self.running():
            self._process_one()


if __name__ == '__main__':
    import threading, atexit
    
    sock = RPCClientSocket()
    
    class Server1(RPCServer):
        def add(self, a, b):
            return a + b
    
    server = Server1(name='some_server', addr='tcp://localhost:5152')
    serve_thread = threading.Thread(target=server.run_forever, daemon=True)
    serve_thread.start()
    
    client = sock.get_client('some_server')
    atexit.register(client.close)
    
    time.sleep(0.2)
    fut = client.add(7, 5)
    assert fut.result() == 12
    
    try:
        client.add(7, 'x').result()
    except RemoteCallException as err:
        if err.type_str != 'TypeError':
            raise
    
    try:
        client.fn().result()
    except RemoteCallException as err:
        if err.type_str != 'AttributeError':
            raise
    
    
    