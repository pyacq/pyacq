import os, sys, re, socket
from pyacq.core.host import Host
from pyacq.core.rpc import RPCServer

usage = """Usage:
    python host_server.py [address]

# Examples:
python host_server.py tcp://10.0.0.100:5000
python host_server.py tcp://10.0.0.100:*
"""

if len(sys.argv) == 2:
    address = sys.argv[1]
else:
    address = ''
    
if not re.match(r'tcp://(\*|([0-9\.]+)):(\*|[0-9]+)', address):
    sys.stderr.write(usage)
    sys.exit(-1)


server = RPCServer(address)
server.run_lazy()
host = Host(name=socket.gethostname(), poll_procs=True)
server['host'] = host
print("Running server at: %s" % server.address.decode())

try:
    server.run_forever()
except KeyboardInterrupt:
    sys.stderr.write("Caught keyboard interrupt, shutting down..\n")
    server.close()
