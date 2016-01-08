from pyacq import create_manager


man = create_manager()
grp = man.create_nodegroup()
node1 = grp.create_node('_MyTestNode')
node2 = grp.create_node('_MyTestNode')
node1.start()
node1.stop()
