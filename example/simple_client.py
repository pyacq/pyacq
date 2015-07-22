from pyacq import create_manager


man = create_manager()
grp = man.create_nodegroup()
node1 = grp.create_node('_MyTestNode')
node2 = grp.create_node('_MyTestNode')
node1.start()
node1.stop()

#for the moment the process continue to live so there is no end
#we shcould avoid this
man.default_host().close()
man.close()