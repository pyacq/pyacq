import logging
import sys
import socket
import os
import threading
import time
import atexit
import traceback

from .remote import get_host_name, get_process_name, get_thread_name


try:
    import colorama
    HAVE_COLORAMA = True
    _ints = [colorama.Style.NORMAL, colorama.Style.BRIGHT, colorama.Style.DIM]
    _fcolors = [colorama.Fore.WHITE, colorama.Fore.GREEN, colorama.Fore.RED,
                colorama.Fore.CYAN, colorama.Fore.YELLOW, colorama.Fore.BLUE,
                colorama.Fore.MAGENTA]
    _bcolors = [colorama.Back.WHITE, colorama.Back.GREEN, colorama.Back.RED,
                colorama.Back.CYAN, colorama.Back.YELLOW, colorama.Back.BLUE,
                colorama.Back.MAGENTA]
    _thread_color_list = [i+c for i in _ints for c in _fcolors[1:]]  # skip white
    
    _level_color_map = {
        0: colorama.Style.DIM + colorama.Fore.WHITE,
        logging.DEBUG: colorama.Style.DIM + colorama.Fore.WHITE,
        logging.INFO: colorama.Style.BRIGHT + colorama.Fore.WHITE,
        logging.WARNING: colorama.Style.BRIGHT + colorama.Fore.YELLOW,
        logging.ERROR: colorama.Style.BRIGHT + colorama.Fore.RED,
        logging.CRITICAL: colorama.Back.RED,
    }    
except ImportError:
    HAVE_COLORAMA = False
    

class RPCLogHandler(logging.StreamHandler):
    """StreamHandler that sorts incoming log records by their creation time
    and writes to stderr. Messages are also colored by their log level and
    the host/process/thread that created the record.
    
    Credit: https://gist.github.com/kergoth/813057
    
    Parameters
    ----------
    stream : file-like
        The stream to which messages should be sent. The default is sys.stderr.
    """
    thread_headers = {}

    def __init__(self, stream=sys.stderr):
        if HAVE_COLORAMA:
            logging.StreamHandler.__init__(self, colorama.AnsiToWin32(stream).stream)
        else:
            logging.StreamHandler.__init__(self, stream)
        
        # Hold log records for 0.5 sec before printing them to allow sorting
        # by creation time.
        self.delay = 0.2
        self.record_lock = threading.Lock()
        self.records = []
        self.thread = threading.Thread(target=self.poll_records, daemon=True)
        self.thread.start()
        atexit.register(self.flush_records)

    @property
    def is_tty(self):
        isatty = getattr(self.stream, 'isatty', None)
        return isatty and isatty()

    def emit(self, record):
        # send record to sorting thread
        with self.record_lock:
            self.records.append(record)
            self.records.sort(key=lambda rec: rec.created)

    def poll_records(self):
        while True:
            # collect all records more than 0.5 sec old
            limit = time.time() - self.delay
            recs = []
            with self.record_lock:
                while len(self.records) > 0 and self.records[0].created < limit:
                    recs.append(self.records.pop(0))
                    
            # emit records or sleep
            if len(recs) > 0:
                for rec in recs:
                    logging.StreamHandler.emit(self, rec)
            else:
                time.sleep(0.2)

    def format(self, record):
        header = self.get_thread_header(record)
        
        message = logging.StreamHandler.format(self, record)
        if HAVE_COLORAMA:
            ind = record.levelno // 10 * 10  # decrease to multiple of 10
            message = _level_color_map[ind] + message + colorama.Style.RESET_ALL
            
        return header + ' ' + message

    def get_thread_header(self, record):
        hid = getattr(record, 'hostname', get_host_name())
        pid = getattr(record, 'process_name', get_process_name())
        tid = getattr(record, 'thread_name', get_thread_name(record.thread))
        key = (hid, pid, tid)
        header = self.thread_headers.get(key, None)
        if header is None:
            header = '[%s:%s:%s]' % (hid, pid, tid)
            if HAVE_COLORAMA:
                color = _thread_color_list[len(self.thread_headers) % len(_thread_color_list)]
                header = color + header + colorama.Style.RESET_ALL
            self.thread_headers[key] = header
        return header

    def colorize(self, message, record):
        if not HAVE_COLORAMA:
            return message
        
        try:
            tid = threading.current_thread().ident
            color = RPCLogHandler.thread_colors.get(tid, None)
            if color is None:
                ind = len(RPCLogHandler.thread_colors) % len(_color_list)
                ind = ind//10*10  # decrease to multiple of 10
                color = _color_list[ind]
                RPCLogHandler.thread_colors[tid] = color
            return (color + message + colorama.Style.RESET_ALL)
        except KeyError:
            return message

    def flush_records(self):
        with self.record_lock:
            while len(self.records) > 0:
                rec = self.records.pop(0)
                logging.StreamHandler.emit(self, rec)


_sys_excepthook = None


def _log_unhandled_exception(exc, val, tb):
    global _sys_excepthook
    exc_str = traceback.format_stack()
    exc_str += [" < exception caught here >\n"]
    exc_str += traceback.format_exception(exc, val, tb)[1:]
    exc_str = ''.join(['    ' + line for line in exc_str])
    logging.getLogger().warn("Unhandled exception:\n%s", exc_str)
    #_sys_excepthook(exc, val, tb)


def log_exceptions():
    """Install a hook that creates log messages from unhandled exceptions.
    """
    global _sys_excepthook
    if sys.excepthook is _log_unhandled_exception:
        return
    _sys_excepthook = sys.excepthook
    sys.excepthook = _log_unhandled_exception
