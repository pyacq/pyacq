"""Script for bootstrapping new processes created with ProcessSpawner.
"""
import zmq
import time
import sys
import json
import traceback
import faulthandler
import logging

# Load configuration options for this process from stdin
conf = json.loads(sys.stdin.read())

# Set up some basic debugging support before importing pyacq
faulthandler.enable()
logger = logging.getLogger()
logger.level = conf['loglevel']

import pyacq
from pyacq.core.rpc import log

# Start QApplication if requested
if conf['qt']:
    import pyqtgraph as pg
    app = pg.mkQApp()
    app.setQuitOnLastWindowClosed(False)

# Set up log record forwarding
if conf['procname'] is not None:
    log.set_process_name(conf['procname'])
if conf['logaddr'] is not None:
    log.set_logger_address(conf['logaddr'].encode())

# Also send unhandled exceptions to log server
log.log_exceptions()

logger.info("New process {procname} {class_name}({args}) log_addr:{logaddr} log_level:{loglevel}".format(**conf))

# Open a socket to parent process to inform it of the new RPC server address
bootstrap_sock = zmq.Context.instance().socket(zmq.PAIR)
bootstrap_sock.connect(conf['bootstrap_addr'].encode())
bootstrap_sock.linger = 1000

# Create RPC server
try:
    # Create server
    server_class = getattr(pyacq, conf['class_name'])
    server = server_class(**conf['args'])
    status = {'address': server.address.decode()}
except:
    logger.error("Error starting {class_name} with args: {args}:".format(**conf))
    status = {'error': traceback.format_exception(*sys.exc_info())}
    
# Report server status to spawner
start = time.time()
while time.time() < start + 10.0:
    # send status repeatedly until spawner gives a reply.
    bootstrap_sock.send_json(status)
    try:
        bootstrap_sock.recv(zmq.NOBLOCK)
        break
    except zmq.error.Again:
        time.sleep(0.01)
        continue

bootstrap_sock.close()

# Run server until heat death of universe
if 'address' in status:
    server.run_forever()
    
if conf['qt']:
    app.exec_()
