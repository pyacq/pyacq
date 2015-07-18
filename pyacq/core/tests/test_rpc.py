import threading, atexit, time
from pyacq.core.rpc import RPCClientSocket, RemoteCallException, RPCServer


def test_rpc():
    class Server1(RPCServer):
        def add(self, a, b):
            return a + b

    server = Server1(addr='tcp://*:5152')
    def process_server():
        while server.running():
            server._process_one()
        print("\nserver shut down\n")
    serve_thread = threading.Thread(target=process_server, daemon=True)
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


if __name__ == '__main__':
    test_rpc()
