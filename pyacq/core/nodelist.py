# TODO find something fancy do resgister in another Host/Process

all_nodes = { }
def register_node(node_class):
    all_nodes[node_class.__name__] = node_class