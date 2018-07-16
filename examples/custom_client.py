"""
Custom RPC client

Demonstrate the most simple use of zmq and json to create a client that
connects to an RPCServer. This provides a basic template for connecting
to pyacq from non-Python platforms.

One important note before we start: pyacq's remote API is not actually different
from its internal Python API. Any function you can call from within Python
can also be invoked remotely by RPC calls. The example below deals entirely
with pyacq's RPC protocol--how translate between the Python API and the raw
packets handled by zeroMQ.
"""

# First we will start a manager in a subprocess to test our client against
from pyacq.core import create_manager
manager = create_manager('rpc')
address = manager._rpc_addr


# --- From here on, we don't use any pyacq code ---
import json, zmq

# Here's how we connect to a new server (we will likely want to connect to
# multiple servers)
def create_socket(address, name):
    """Return a ZeroMQ socket connected to an RPC server.
    
    Parameters
    ----------
    address : str
        The zmq interface where the server is listening (e.g.
        'tcp://127.0.0.1:5678')
    name : str
        A unique name identifying the client. 
    """
    if isinstance(name, str):
        name = name.encode()
    socket = zmq.Context.instance().socket(zmq.DEALER)
    socket.setsockopt(zmq.IDENTITY, name)
    socket.setsockopt(zmq.RCVTIMEO, 5000)  # 5 sec timeout

    # Connect the socket to the server
    if isinstance(address, str):
        address = address.encode()
    socket.connect(address)
    
    # Ping the server until it responds to make sure we are connected.
    ping(socket)
    print("\nConnected to server @ %s" % address)    
    
    return socket
    
    
# Here's how we have to format all request messages that we send to RPC servers
next_req_id = 0
def send(socket, action, opts=None, request_response=True, return_type='auto'):
    """Send a request to an RPC server.
    
    Parameters
    ----------
    socket : zmq socket
        The ZeroMQ socket that is connected to the server. 
    action : str
        Name of action server should perform. See :func:`RPCClient.send()` for
        a list of actions and their associated options.
    opts : dict or None
        An optional dict of options specifying the behavior of the action.
    request_response : bool
        If True, then the server is asked to send a response.
    return_type : str
        'proxy' to force the server to send return values by proxy, or 'auto'
        to allow the server to decide whether to return by proxy or by value.
    """
    global next_req_id
    
    # If we want the server to send a response, then we must supply a unique ID
    # for the request. Otherwise, send -1 as the request ID to indicate that
    # the server should not send a reply.
    if request_response:
        req_id = next_req_id
        next_req_id += 1
    else:
        req_id = -1
    
    # Serialize opts if it was specified, otherwise send an empty string. 
    if opts is None:
        opts_str = b''
    else:
        opts_str = json.dumps(opts).encode()
    
    # Tell the server which serializer we are using
    ser_type = b'json'
    
    # Send the request as a multipart message
    msg = [str(req_id).encode(), action.encode(), return_type.encode(), ser_type, opts_str]
    socket.send_multipart(msg)

    # Print so we can see what the final json-encoded message looks like
    msg = '\n'.join(['    ' + m.decode() for m in msg])
    print("\n>>> send to %s:\n%s" % (socket.last_endpoint.decode(), msg))
    
    # Return the request ID we can use to listen for a response later.
    return req_id


# ..And here is how we receive responses from the server.
def recv(socket):
    # Wait for a response or a timeout.
    try:
        msg = socket.recv().decode()
    except zmq.error.Again:
        raise TimeoutError('Timed out while waiting for server response.')

    # Print so we can see what the json-encoded message looks like
    print("\n<<< recv from %s:\n    %s" % (socket.last_endpoint.decode(), msg))

    # Unserialize the response
    msg = json.loads(msg)
    
    # Check for error
    if msg.get('error', None) is not None:
        traceback = ''.join(msg['error'][1])
        raise RuntimeError("Exception in remote process:\n%s" % traceback)
    
    # NOTE: msg also contains the key 'req_id', which should be used to verify
    # that the message received really does correspond to a particular request.
    # We're skipping that here for simplicity.
    
    return msg['rval']


def get_attr(socket, obj, attr_name):
    """Return an attribute of an object owned by a remote server.
    
    Parameters
    ----------
    socket : zmq socket
        A socket that is connected to the remote server.
    obj : dict
        A dict that identifies the object owned by the server.
    attr_name : str
        The name of the attribute to return. 
    """
    attr = obj.copy()
    attr['attributes'] = (attr_name,)
    send(socket, action='get_obj', opts={'obj': attr})
    return recv(socket)


def call_method(socket, obj, method_name, *args, **kwds):
    """Request that a remote server call a method on an object.
    
    Parameters
    ----------
    socket : zmq socket
        A socket that is connected to the remote server.
    obj : dict
        A dict that identifies the object owned by the server. This should have
        been returned by a previous request to the server.
    method_name : str
        The name of the method to call.
    args,kwargs : 
        All further arguments are passed to the remote method call.
    """
    # modify object reference to point to its method instead.
    # (this is faster than using get_attr as defined above)
    func = obj.copy()
    func['attributes'] = (method_name,)
    send(socket, action='call_obj', opts={'obj': func, 'args': args, 'kwargs': kwds})
    return recv(socket)
    

def ping(socket):
    """Ping a server until it responds.
    
    This can be called to check that a functional connection to a server exists
    before making any other requests.
    """
    for i in range(3):
        req_id = send(socket, action='ping')
        try:
            resp = recv(socket)
            assert resp == 'pong'
            break
        except TimeoutError:
            pass
        if i == 2:
            raise RuntimeError("Did not receive any response from server at %s!"
                % socket.last_endpoint)




# Create a zmq socket with a unique name
socket = create_socket(address, 'my_custom_client')

# Request a reference to the manager
send(socket, action='get_item', opts={'name': 'manager'})
manager = recv(socket)

# Ask the manager to create a nodegroup
nodegroup = call_method(socket, manager, 'create_nodegroup', name='my_nodegroup')

# Request from the manager a list of all available nodegroups
ng_list = call_method(socket, manager, 'list_nodegroups')
assert ng_list[0] == nodegroup

# Connect to the newly spawned nodegroup and ask it a question
ng_socket = create_socket(nodegroup['rpc_addr'], 'my_nodegroup_socket')    
node_types = call_method(ng_socket, nodegroup, 'list_node_types')
print("\nAvailable node types: %s" % node_types)

