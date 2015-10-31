from .log import *
from .monitor import LogWidget

from ..rpc.log import LogSender, LogReceiver

# for sending messages to a LogReceiver via RPCServer
log_handler = LogSender()

logger = logging.getLogger('pyacq')
#handler = ColorizingStreamHandler(sys.stdout)
#logger.addHandler(handler)
logger.addHandler(log_handler)

logger.level = logging.WARN

info = logger.info
debug = logger.debug
warn = logger.warn
error = logger.error
critical = logger.critical

