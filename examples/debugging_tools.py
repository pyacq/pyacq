"""
This example demonstrates the use of remote logging, exception handling, and
the LogViewer UI. These are intended to simplify the process of debugging in
distributed systems.
"""
import threading, atexit, time, logging, sys
from pyacq.core.rpc import RPCClient, RemoteCallException, RPCServer, QtRPCServer, ObjectProxy, ProcessSpawner, ThreadSpawner
from pyacq.core.rpc.log import RPCLogHandler, set_process_name, set_thread_name, start_log_server, log_exceptions
from pyacq.core.rpc.log.logviewer import LogViewer

import pyqtgraph as pg
#pg.dbg()

logger = logging.getLogger()
logger.level = logging.DEBUG

# Start a server that will receive log messages from other processes
start_log_server(logger)

# Generate a log message for uncaught exceptions in this process.
log_exceptions()

# Set names for this process/thread so that messages originating locally can be
# easily identified
set_process_name('main_process')
set_thread_name('main_thread')

qapp = pg.mkQApp()

# Create a ui that displays all incoming log messages
lv = LogViewer()
lv.show()

# generate some local log messages
logger.info(__doc__)

logger.info(">>>> Create 4 log messages of differing level:")
logger.debug("debug")
logger.info("info")
logger.warn("warn")
logger.error("error")

# raise an exception locally
logger.info(">>>> Raise an exception in the main process:")
try:
    raise Exception("local exception")
except:
    sys.excepthook(*sys.exc_info())

# start a new thread in this process
logger.info(">>>> Spawn a new thread:")
th = ThreadSpawner(name="thread1")

# cause an exception in the thread
logger.info(">>>> Cause an exception in the remote thread:")
try:
    th.client._import('xxxxx')
except:
    sys.excepthook(*sys.exc_info())


logger.info(">>>> Spawn a new process:")
proc = ProcessSpawner(name='proc1')

logger.info(">>>> Cause an exception in the remote process:")
proc.client._import('xxxxx')


#rlogging = proc.client._import('logging')
#rlogger = rlogging.getLogger()
#rlogger.warn('test exception')
#time.sleep(0.3)
#qapp.processEvents()
#rec = lv.log_records[-5]
#print("msg:\n%s" % rec.getMessage())
#print("\nexc_info: \n%s" % rec.stack)




