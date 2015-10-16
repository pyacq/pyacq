import sys
import time
import traceback
import zmq
from logging import info

from .serializer import serializer


class RPCServer(object):
    """RPC server for invoking requests on proxied objects.
    
    Parameters
    ----------
    name : str
        Name used to identify this server.
    addr : URL
        Address for RPC server to bind to.
    """
    def __init__(self, name, addr):
        self._name = name.encode()
        self._socket = zmq.Context.instance().socket(zmq.ROUTER)
        self._socket.setsockopt(zmq.IDENTITY, self._name)
        self._socket.bind(addr)
        self._addr = self._socket.getsockopt(zmq.LAST_ENDPOINT)
        self._closed = False
        
        # Objects that may be retrieved by name using client['obj_name']
        self._namespace = {}
        
        info("RPC start server: %s@%s", self._name.decode(), self._addr.decode())

    def __del__(self):
        self._socket.close()

    def _read_and_process_one(self):
        """Read one message from the remote client and invoke the requested
        action.
        
        This method sends back to the client either the return value or an
        error message.
        """
        name, msg = self._read_socket()
        self._process_one(name, msg)
        
    def _read_socket(self):
        """Read one message from the remote client
        """
        if not self.running:
            raise RuntimeError("RPC server socket is already closed.")
            
        name, msg = self._socket.recv_multipart()
        info("RPC recv req: %s %s", name, msg)
        return name, msg
        
    def _process_one(self, name, msg):
        """
        Invoke the requested action.
        """
        msg = serializer.loads(msg)
        if msg['action'] == 'call':
            method, args = msg['args'][0], msg['args'][1:]
            kwds = msg['kwds']
            ret = kwds.pop('_return', True)
            try:
                call_id = msg['call_id']
                fn = getattr(self, method)
                if len(kwds) == 0:
                    # need to do this because some functions do not allow
                    # keyword arguments.
                    rval = fn(*args)
                else:
                    rval = fn(*args, **kwds)
                if ret:
                    self._send_result(*self._format_result(name, call_id, rval=rval))
            except:
                exc_str = ["Error while processing request %s.%s(%s, %s)" % (str(self), method, args, kwds)]
                exc_str += traceback.format_stack()
                exc_str += [" < exception caught here >\n"]
                exc = sys.exc_info()
                exc_str += traceback.format_exception(*exc)
                if ret:
                    self._send_result(*self._format_result(name, call_id, error=(exc[0].__name__, exc_str)))
    
    def _format_result(self, name, call_id, rval=None, error=None):
        result = {'action': 'return', 'call_id': call_id,
                  'rval': rval, 'error': error}
        info("RPC send res: %s %s", name, result)
        return name, serializer.dumps(result)
    
    def _send_result(self, name, data):
        self._socket.send_multipart([name, data])

    def close(self):
        """Close this RPC server.
        """
        self._closed = True
        # keep the socket open just long enough to send a confirmation of
        # closure.

    def running(self):
        """Boolean indicating whether the server is still running.
        """
        return not self._closed
    
    def run_forever(self):
        while self.running():
            self._read_and_process_one()

    def ping(self):
        return 'pong'
