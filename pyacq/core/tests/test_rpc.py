import threading, atexit, time
from pyacq.core.rpc import RPCClient, RemoteCallException, RPCServer
import zmq.utils.monitor


def test_rpc():
    class Server1(RPCServer):
        def add(self, a, b):
            return a + b
        def sleep(self, t):
            time.sleep(t)

    server = Server1(name='some_server', addr='tcp://*:5152')
    serve_thread = threading.Thread(target=server.run_forever, daemon=True)
    serve_thread.start()
    
    client = RPCClient('some_server', 'tcp://localhost:5152')
    atexit.register(client.close)
    
    # test call / return
    fut = client.add(7, 5)
    assert fut.result() == 12

    fut = client.sleep(0.1)
    assert not fut.done()
    assert fut.result() is None

    # Test remote exception raising
    try:
        client.add(7, 'x').result()
    except RemoteCallException as err:
        if err.type_str != 'TypeError':
            raise
    else:
        raise AssertionError('should have raised TypeError')

    try:
        client.fn().result()
    except RemoteCallException as err:
        if err.type_str != 'AttributeError':
            raise
    else:
        raise AssertionError('should have raised AttributeError')

    # test timeouts
    try:
        client.sleep(0.2).result(timeout=0.01)
    except TimeoutError:
        pass
    else:
        raise AssertionError('should have raised TimeoutError')

    # test result order
    a = client.add(1, 2)
    b = client.add(3, 4)
    assert b.result() == 7
    assert a.result() == 3

    # test multiple clients per server
    client2 = RPCClient('some_server', 'tcp://localhost:5152')
    
    a = client2.add(1, 2)
    b = client.add(3, 4)
    c = client2.add(5, 6)
    assert b.result() == 7
    assert a.result() == 3
    assert c.result() == 11

    # test multiple clients sharing one socket
    server2 = Server1(name='some_server2', addr='tcp://*:5153')
    serve_thread2 = threading.Thread(target=server2.run_forever, daemon=True)
    serve_thread2.start()
    
    client3 = RPCClient('some_server2', 'tcp://localhost:5153',
                        shared_client=client2)
    
    a = client2.add(1, 2)
    b = client3.add(3, 4)
    assert b.result() == 7
    assert a.result() == 3


if __name__ == '__main__':
    test_rpc()
