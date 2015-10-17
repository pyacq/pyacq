import time
import weakref
import concurrent.futures
from logging import info
import zmq

from .client_socket import RPCClientSocket
from .serializer import MsgpackSerializer


class RPCClient(object):
    """Connection to an RPC server.
    
    This class is a proxy for methods provided by the remote server. It is
    meant to be used by accessing and calling remote procedure names::
    
        client = RPCClient('tcp://localhost:5274')
        future = client.my_remote_procedure_name(...)
        result = future.result()
        
    Parameters
    ----------
    name : str
        The identifier used by the remote server.
    addr : URL
        Address of RPC server to connect to.
    rpc_socket : None or RPCClientSocket
        Optional RPCClientSocket with which to connect to the server. This
        allows multiple RPC connections to share a single socket.
    """
    def __init__(self, name, addr):
        # ROUTER is fully asynchronous and may connect to multiple endpoints.
        # We can use ROUTER to allow this socket to connect to multiple servers.
        # However this adds complexity with little benefit, as we can just use
        # a poller to check for messages on multiple sockets if desired.
        #self.socket = zmq.Context.instance().socket(zmq.ROUTER)
        #self._name = ('%d-%x' % (os.getpid(), id(self))).encode()
        #self.socket.setsockopt(zmq.IDENTITY, self._name)
        
        # DEALER is fully asynchronous--we can send or receive at any time, and
        # unlike ROUTER, it only connects to a single endpoint.
        self.socket = zmq.Context.instance().socket(zmq.DEALER)
        self.sock_name = ('%d-%x' % (os.getpid(), id(self))).encode()
        self.socket.setsockopt(zmq.IDENTITY, self._sock_name)
        
        info("RPC connect %s => %s@%s", rpc_socket._name, name, addr)
        self.socket.connect(addr)
        self.next_request_id = 0
        self.futures = weakref.WeakValueDictionary()
        
        self.name = name.encode()
        self.connect_established = False
        self.establishing_connect = False

        # Proxies we have received from other machines. 
        self._proxies = {}

        # For unserializing results returned from servers. This cannot be
        # used to send proxies of local objects unless there is also a server
        # for this thread..
        self._serializer = MsgpackSerializer()

    def send(self, action, return_type='auto', opts=None):
        """Send a request to the remote process.
        
        Parameters
        ----------
        action : str
            The action to invoke on the remote process.
        return_type : 'auto' | 'proxy' | None
            If 'proxy', then the return value is sent by proxy. If 'auto', then
            the server decides based on the return type whether to send a proxy.
            If None, then no response will be sent.
        opts : None or dict
            Extra options to be sent with the request.
        """
        req_id = self.next_request_id
        self.next_request_id += 1
        
        # double-serialize opts to ensure that cmd can be read even if opts
        # cannot.
        # TODO: This might be expensive; a better way might be to send opts in
        # a subsequent packet, but this makes the protocol more complicated..
        opts = self._serializer.dumps(opts)
        cmd = {'action': action, 'req_id': req_id, 'return_type': return_type, 'opts': opts}
        cmd = self._serializer.dumps(cmd)
        
        info("RPC send req: %s => %s, %s", self.socket.getsockopt(zmq.IDENTITY), name, cmd)
        self.socket.send(cmd)
        
        # If using ROUTER, we have to include the name of the endpoint to which
        # we are sending
        #self.socket.send_multipart([name, cmd])
        
        fut = Future(self, req_id)
        self.futures[req_id] = fut
        return fut

    def _ensure_connection(self, timeout=3):
        """Make sure RPC server is connected and available.
        """
        if self._establishing_connect:
            return
        self._establishing_connect = True
        try:
            start = time.time()
            while time.time() < start + timeout:
                fut = self.send('ping')
                try:
                    result = fut.result(timeout=0.1)
                    self._connect_established = True
                    return
                except TimeoutError:
                    continue
            raise TimeoutError("Could not establish connection with RPC server.")
        finally:
            self._establishing_connect = False

    def process(self):
        """Process all available incoming messages.
        
        Return immediately if no messages are available.
        """
        while True:
            try:
                # if using ROUTER, then we receive the name of the endpoint
                # followed by the message
                #name = self.socket.recv(zmq.NOBLOCK)
                #msg = self.socket.recv()
                
                msg = self.socket.recv(zmq.NOBLOCK)
                msg = self._serializer.loads(msg)
                self._process_msg(name, msg)
            except zmq.error.Again:
                break  # no messages left

    def process_until_future(self, future, timeout=None):
        """Process all incoming messages until receiving a result for *future*.
        
        If the future result is not raised before the timeout, then raise
        TimeoutError.
        """
        start = time.perf_counter()
        while not future.done():
            # wait patiently with blocking calls.
            if timeout is None:
                itimeout = -1
            else:
                dt = time.perf_counter() - start
                itimeout = int((timeout - dt) * 1000)
                if itimeout < 0:
                    raise TimeoutError("Timeout waiting for Future result.")
            try:
                self.socket.setsockopt(zmq.RCVTIMEO, itimeout)
                name, msg = self.socket.recv_multipart()
                msg = serializer.loads(msg)
            except zmq.error.Again:
                raise TimeoutError("Timeout waiting for Future result.")
            
            self._process_msg(name, msg)

    def _process_msg(self, msg):
        """Handle one message received from the remote process.
        
        This takes care of assigning return values or exceptions to existing
        Future instances.
        """
        info("RPC recv res: %s %s", msg)
        if msg['action'] == 'return':
            req_id = msg['req_id']
            if req_id not in self.futures:
                return
            fut = self.futures[req_id]
            if msg['error'] is not None:
                exc = RemoteCallException(*msg['error'])
                fut.set_exception(exc)
            else:
                fut.set_result(msg['rval'])
        else:
            raise ValueError("Invalid action '%s'" % msg['action'])
    
    def close(self):
        self.send('release_all', return_type=None) 
        self.socket.close()

    def __del__(self):
        self.close()



class RemoteCallException(Exception):
    def __init__(self, type_str, tb_str):
        self.type_str = type_str
        self.tb_str = tb_str
        
    def __str__(self):
        msg = '\n===> Remote exception was:\n' + ''.join(self.tb_str)
        return msg


class Future(concurrent.futures.Future):
    """Represents a return value from a remote procedure call that has not
    yet arrived.
    
    Use `done()` to determine whether the return value (or an error message)
    has arrived, and `result()` to get the return value (or raise an
    exception).
    """
    def __init__(self, socket, call_id):
        concurrent.futures.Future.__init__(self)
        self.socket = socket
        self.call_id = call_id
    
    def cancel(self):
        return False

    def result(self, timeout=None):
        self.socket.process_until_future(self, timeout=timeout)
        return concurrent.futures.Future.result(self)

