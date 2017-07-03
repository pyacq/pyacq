import sys
import logging

_exception_logger = None


class ExceptionLogger(object):
    def __init__(self, logger=None, log_level=logging.WARN, call_orig_hook=False):

        if logger is None:
            logger = logging.getLogger()
        self.logger = logger

        self.log_level = log_level
        self.call_orig_hook = call_orig_hook
        
    def install(self):
        if sys.excepthook is self.log_exception:
            return
        self.orig_hook = sys.excepthook
        sys.excepthook = self.log_exception

    def uninstall(self):
        if sys.excepthook is not self.log_exception:
            return
        sys.excepthook = self.orig_hook
        self.orig_hook = None
                              
    def log_exception(self, exc, val, tb):
        logger = self.logger
        if logger is not None:
            extra = {'exc_info': (exc, val, tb)}
            logger.log(self.log_level, "Unhandled exception: %s", str(exc), extra=extra)
        if self.call_orig_hook:
            self.orig_hook(exc, val, tb)


def log_exceptions(logger=None, log_level=logging.WARN, call_orig_hook=False):
    """Install a hook that creates log messages from unhandled exceptions.
    """
    global _exception_logger
    if _exception_logger is None:
        _exception_logger = ExceptionLogger(logger, call_orig_hook)
    _exception_logger.install()
