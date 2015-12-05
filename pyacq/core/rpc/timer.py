import time
import threading

from .proxy import ObjectProxy
import logging
logger = logging.getLogger()

class Timer(object):
    """Timer for making scheduled callbacks in a new thread.
    
    Parameters
    ----------
    callback : callable
        Any callable object to be called on a timed schedule. Will be called
        from a new thread, so this must be a thread-safe callable such as an
        ObjectProxy.
    interval : float
        Minimum time to wait between callback invocations (start to start).
    limit : int or None
        Optional maximum number of times to invoke the callback.
    start : bool
        Whether to immediately start the timer.
    """
    def __init__(self, callback, interval, limit=None, start=False):
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.callback = callback
        self.interval = float(interval)
        self.limit = limit
        self._last_call_time = None
        self._call_count = 0
        self._lock = threading.Lock()
        
        if start:
            self.start()
            
    def start(self):
        """Start the timer.
        
        This method begins a new thread that will sleep between callback
        invocations.
        """
        with self._lock:
            self.running = True
            self._last_call_time = None
            self._call_count = 0
        
        if self.thread.is_alive():
            return
        else:
            self.thread.start()
        
    def stop(self):
        """Stop the timer.
        """
        with self._lock:
            self.running = False
        
    def _run(self):
        try:
            callback = self.callback
            if isinstance(callback, ObjectProxy):
                # Make sure we are using a proxy owned by this thread
                callback = callback._copy()
            
            while True:
                if self._last_call_time is None:
                    sleep_time = 0
                else:
                    sleep_time = self.interval - (time.perf_counter() - self._last_call_time)
                
                if sleep_time > 0:
                    time.sleep(sleep_time)
                    
                with self._lock:
                    if not self.running:
                        return
                    self._last_call_time = time.perf_counter()
                    
                callback()
                
                with self._lock:
                    self._call_count += 1
                    if self.limit is not None and self._call_count >= self.limit:
                        return
        finally:
            with self._lock:
                self.running = False
