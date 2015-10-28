import socket
import logging
import sys
import os
import threading

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
    

class ColorizingStreamHandler(logging.StreamHandler):
    """Credit: https://gist.github.com/kergoth/813057
    """
    thread_headers = {}

    def __init__(self, stream):
        if HAVE_COLORAMA:
            logging.StreamHandler.__init__(self, colorama.AnsiToWin32(stream).stream)
        else:
            logging.StreamHandler.__init__(self, stream)
    
    @property
    def is_tty(self):
        isatty = getattr(self.stream, 'isatty', None)
        return isatty and isatty()

    def format(self, record):
        tid = threading.current_thread().ident        
        header = self.get_thread_header(tid)
        
        message = logging.StreamHandler.format(self, record)
        if HAVE_COLORAMA:
            ind = record.levelno//10*10  # decrease to multiple of 10
            message = _level_color_map[ind] + message + colorama.Style.RESET_ALL
            
        return header + ' ' + message

    def get_thread_header(self, tid):
        header = self.thread_headers.get(tid, None)
        if header is None:
            header = '[%s:%d.%x]' % (socket.gethostname(), os.getpid(), tid)
            if HAVE_COLORAMA:
                color = _thread_color_list[len(self.thread_headers) % len(_thread_color_list)]
                header = color + header + colorama.Style.RESET_ALL
            self.thread_headers[tid] = header
        return header

    def colorize(self, message, record):
        if not HAVE_COLORAMA:
            return message
        
        try:
            tid = threading.current_thread().ident
            color = ColorizingStreamHandler.thread_colors.get(tid, None)
            if color is None:
                ind = len(ColorizingStreamHandler.thread_colors) % len(_color_list)
                ind = ind//10*10  # decrease to multiple of 10
                color = _color_list[ind]
                ColorizingStreamHandler.thread_colors[tid] = color
            return (color + message + colorama.Style.RESET_ALL)
        except KeyError:
            return message


logger = logging.getLogger('pyacq')
handler = ColorizingStreamHandler(sys.stdout)
logger.addHandler(handler)

logger.level = logging.WARN

info = logger.info
debug = logger.debug
warn = logger.warn
error = logger.error
critical = logger.critical
