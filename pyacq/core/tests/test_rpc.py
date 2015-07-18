import threading, atexit, time
from pyacq.core.rpc import RPCClient, RemoteCallException, RPCServer
import zmq.utils.monitor


def test_rpc():
    class Server1(RPCServer):
        def add(self, a, b):
            return a + b

    server = Server1(name='some_server', addr='tcp://*:5152')
    serve_thread = threading.Thread(target=server.run_forever, daemon=True)
    serve_thread.start()

    client = RPCClient('some_server', 'tcp://localhost:5152')
    atexit.register(client.close)
    
    #mon = client._socket.socket.get_monitor_socket()
    #def monitor():
        #while mon.poll():
            #evt = zmq.utils.monitor.recv_monitor_message(mon)
            #print("MON:", evt)
    #mon_thread = threading.Thread(target=monitor, daemon=True)
    #mon_thread.start()
            

    time.sleep(0.4)
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
