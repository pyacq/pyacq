all_transfermodes = {}

def register_transfermode(modename, sender, receiver):
    global all_transfermodes
    all_transfermodes[modename] = (sender, receiver)


class DataSender:
    """Base class for OutputStream data senders.

    Subclasses are used to implement different methods of data transmission.
    """
    def __init__(self, socket, params):
        self.socket = socket
        self.params = params
        self.funcs = []

    def send(self, index, data):
        raise NotImplementedError()
    
    def close(self):
        pass


class DataReceiver:
    """Base class for InputStream data receivers.

    Subclasses are used to implement different methods of data transmission.
    """
    def __init__(self, socket, params):
        self.socket = socket
        self.params = params
        self.buffer = None
            
    def recv(self, return_data=False):
        raise NotImplementedError()
    
    def close(self):
        pass
    
