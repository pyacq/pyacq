import socket
import sys
import threading
import os
import zmq
import logging
import time
logger = logging.getLogger(__name__)
logger.propagate = False

from ..serializer import JsonSerializer

# Provide access to process and thread names for logging purposes.
# Python already has a notion of process and thread names, but these are
# apparently difficult to set. 
host_name = socket.gethostname()
process_name = "process-%d" % os.getpid()
thread_names = {}


def set_host_name(name):
    """Set the name of this host used for logging.
    """
    global host_name
    host_name = name

def get_host_name():
    """Return the name of this host used for logging.
    """
    global host_name
    return host_name

def set_process_name(name):
    """Set the name of this process used for logging.
    """
    global process_name
    process_name = name

def get_process_name():
    """Return the name of this process used for logging.
    """
    global process_name
    return process_name

def set_thread_name(name, tid=None):
    """Set the name of a thread used for logging.
    
    If no thread ID is given, then the current thread's ID is used.
    """
    global thread_names
    if tid is None:
        tid = threading.current_thread().ident
    thread_names[tid] = name

def get_thread_name(tid=None):
    """Return the name of a thread used for logging.
    
    If no thread ID is given, then the current thread's ID is used.
    """
    if tid is None:
        tid = threading.current_thread().ident
    return thread_names.get(tid, 'thread-%x'%tid)
    


# Provide global access to sender / server
server = None
sender = None
server_addr = None


def start_log_server(logger):
    """Create a global log server and attach it to a logger.
    
    Use `get_logger_address()` to return the socket address for the server
    after it has started. On a remote process, call `set_logger_address()` to
    connect it to the server. Then all messages logged remotely will be
    forwarded to the server and handled by the logging system there.
    """
    global server
    if server is not None:
        raise Exception("A global LogServer has already been created.")
    if isinstance(logger, str):
        logger = logging.getLogger(logger)
    server = LogServer(logger)
    server.start()


def get_logger_address():
    """ Return the address of the LogServer used by this process.
    
    If a LogServer has been created in this process, then its address is
    returned. Otherwise, the last address set with `set_logger_address()`
    is used.
    """
    global server, server_addr
    if server is None:
        return server_addr
    else:
        return server.address
    
    
def set_logger_address(addr):
    """Set the address to which all log messages should be sent.
    
    This function creates a global LogSender and attaches it to the root logger.
    """
    global sender, server_addr
    if sender is not None:
        raise Exception("A global LogSender has already been created.")
    sender = LogSender(addr, '')
    server_addr = addr


class LogSender(logging.Handler):
    """Handler for forwarding log messages to a remote LogServer via zmq socket.
    
    Instances of this class can be attached to any python logger using
    `logger.addHandler(log_sender)`.
    
    This can be used with `LogServer` to collect log messages from many remote
    processes to a central logger.
    
    Note: We do not use RPC for this because we have to avoid generating extra
    log messages.
    
    Parameters
    ----------
    address : str | None
        The socket address of a log server. If None, then the sender is
        not connected to a server and `connect()` must be called later.
    logger : str | None
        The name of the python logger to which this handler should be attached.
        If None, then the handler is not attached (use '' for the root logger).
    
    """
    def __init__(self, address=None, logger=None):
        self.socket = None
        self.serializer = JsonSerializer()
        logging.Handler.__init__(self)
        
        if address is not None:
            self.connect(address)
            
        # attach to logger if requested
        if isinstance(logger, str):
            logger = logging.getLogger(logger)
        if logger is not None:
            logger.addHandler(self)

    def handle(self, record):
        global host_name, process_name, thread_names
        if self.socket is None:
            return
        rec = record.__dict__.copy()
        rec['msg'] = rec['msg'] % rec.pop('args')
        if process_name is not None:
            rec['process_name'] = process_name
        rec['thread_name'] = thread_names.get(rec['thread'], rec['threadName'])
        rec['host_name'] = host_name
        self.socket.send(self.serializer.dumps(rec))
        
    def connect(self, addr):
        """Set the address of the LogServer to which log messages should be
        sent. This value should be acquired from `log_server.address` or
        `get_logger_address()`.
        """
        self.socket = zmq.Context.instance().socket(zmq.PUSH)
        self.socket.connect(addr)


class LogServer(threading.Thread):
    """Thread for receiving log records via zmq socket.
    
    Messages are immediately passed to a python logger for local handling.
    
    Parameters
    ----------
    logger : Logger
        The python logger that should handle incoming messages.
    """
    def __init__(self, logger, sort=True):
        threading.Thread.__init__(self, daemon=True)
        self.logger = logger
        self.socket = zmq.Context.instance().socket(zmq.PULL)
        self.socket.bind('tcp://*:*')
        self.address = self.socket.getsockopt(zmq.LAST_ENDPOINT)
        self.serializer = JsonSerializer()
        
    def run(self):
        while True:
            msg = self.socket.recv()
            kwds = self.serializer.loads(msg)
            rec = logging.makeLogRecord(kwds)
            self.logger.handle(rec)
