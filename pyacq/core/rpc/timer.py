import time
import threading


class Timer(threading.Thread):
    """Thread for making scheduled RPC calls.
    """
    def __init__(self, callback, interval, limit=None, start=False):
        threading.Thread.__init__(self, daemon=True)
        self.callback = callback
        self.interval = float(interval)
        self.limit = limit
        self._last_call_time = None
        self._call_count = 0
        self._lock = threading.Lock()
        
        if start:
            self.start()
            
    def start(self):
        with self._lock:
            self.running = True
            self._last_call_time = None
            self._call_count = 0
        
        if self.is_alive():
            return
        else:
            self.start()
        
    def stop(self):
        with self._lock:
            self.running = False
        
    def run(self):
        try:
            if self._last_call_time is None:
                sleep_time = 0
            else:
                sleep_time = self.interval - (time.perf_counter() - self._last_call_time)
            
            if sleep_time > 0:
                time.sleep(sleep_time)
                
            with self._lock:
                if not self.running:
                    return
            
            self.callback()
            
            with self._lock:
                self._call_count += 1
                if self._call_count >= self.limit:
                    return
        finally:
            with self._lock:
                self.running = False
