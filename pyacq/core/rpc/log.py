import threading
import zmq
import logging
logger = logging.getLogger(__name__)
logger.propagate = False

from .serializer import MsgpackSerializer

# Provide access to process and thread names for logging purposes.
# Python already has a notion of process and thread names, but these are
# apparently difficult to set. 
process_name = None
thread_names = {}

def set_process_name(name):
    global process_name
    process_name = name

def set_thread_name(name, tid=None):
    global thread_names
    if tid is None:
        tid = threading.current_thread().ident
    thread_names[tid] = name


# Provide global access to sender / receiver
receiver = None
sender = None
recevier_addr = None


def start_receiver(logger):
    """Create a global log receiver and attach it to a logger.
    """
    global receiver
    if receiver is not None:
        raise Exception("A global LogReceiver has already been created.")
    if isinstance(logger, str):
        logger = logging.getLogger(logger)
    receiver = LogReceiver(logger)


def get_receiver_address():
    """ Return the address of the LogReceiver used by this process.
    
    If a LogReceiver has been created in this process, then its address is
    returned. Otherwise, the last address set with `set_receiver_address()`
    is used.
    """
    global receiver, receiver_addr
    if receiver is None:
        return receiver_addr
    else:
        return receiver.address
    
    
def set_receiver_address(addr):
    """Set the address to which all log messages should be sent.
    
    This function creates a global LogSender and attaches it to the root logger.
    """
    global sender, receiver_addr
    if sender is not None:
        raise Exception("A global LogSender has already been created.")
    sender = LogSender(addr, '')
    receiver_addr = addr


class LogSender(logging.Handler):
    """Handler for forwarding log messages to a remote LogReceiver via zmq socket.
    
    Instances of this class can be attached to any python logger using
    `logger.addHandler(log_sender)`.
    
    This can be used with `LogReceiver` to collect log messages from many remote
    processes to a central logger.
    
    Note: We do no use RPC for this because we have to avoid generating extra
    log messages.
    
    Parameters
    ----------
    address : str | None
        The socket address of a log receiver. If None, then the sender is
        not connected to a receiver and `set_receiver()` must be called later.
    logger : str | None
        The name of the python logger to which this handler should be attached.
        If None, then the handler is not attached (use '' for the root logger).
    
    """
    def __init__(self, address=None, logger=None):
        self.socket = None
        self.serializer = MsgpackSerializer()
        logging.Handler.__init__(self)
        
        if address is not None:
            self.set_receiver(address)
        if logger is not None:
            logging.getLogger(logger).addHandler(self)

    def handle(self, record):
        global process_name, thread_names
        if self.socket is None:
            return
        rec = record.__dict__.copy()
        rec['msg'] = rec['msg'] % rec.pop('args')
        if process_name is not None:
            rec['processName'] = process_name
        rec['threadName'] = thread_names.get(rec['thread'], rec['threadName'])
        self.socket.send(self.serializer.dumps(rec))
        
    def set_receiver(self, addr):
        """Set the address of the LogReceiver to which log messages should be
        sent. This value should be acquired from `log_receiver.address`.
        """
        self.socket = zmq.Context.instance().socket(zmq.PUSH)
        self.socket.connect(addr)


class LogReceiver(threading.Thread):
    """Thread for receiving log records via zmq socket.
    
    Parameters
    ----------
    logger : Logger
        The python logger that should handle incoming messages.
    """
    def __init__(self, logger):
        threading.Thread.__init__(self, daemon=True)
        self.logger = logger
        self.socket = zmq.Context.instance().socket(zmq.PULL)
        self.socket.bind('tcp://*:*')
        self.address = self.socket.getsockopt(zmq.LAST_ENDPOINT)
        self.serializer = MsgpackSerializer()
        
    def run(self):
        while True:
            kwds = self.serializer.loads(self.socket.recv())
            print(kwds)
            rec = logging.makeLogRecord(kwds)
            self.logger.handle(rec)
