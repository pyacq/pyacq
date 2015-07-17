from .rpc import RPCServer

class Manager(RPCServer):
    """
    This class:
       * centralize the all rpc commands to distribite them
       * centralize all info about all Node, NodeGroup, Host, ...
    """
    def __init__(self, name, addr):
        RPCServer.__init__(self, name, addr)
