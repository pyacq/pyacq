# TODO find something fancy do resgister in another Host/Process

all_nodes = {}


def register_node_type(node_class, classname=None):
    if classname is None:
        classname = node_class.__name__
    assert classname not in all_nodes, 'Class {} already resitered'.format(classname)
    all_nodes[classname] = node_class
