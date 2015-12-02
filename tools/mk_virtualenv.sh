# set up new virtualenv with all ppip-installable packages
virtualenv --python=python3.4 venv
. venv/bin/activate
pip install pyzmq pytest numpy scipy pyqtgraph vispy colorama msgpack-python pyaudio

# copy sip and pyqt from system packages (these are not pip installable)
cp -r /usr/lib/python3/dist-packages/sip* venv/lib/python3.4/site-packages/
cp -r /usr/lib/python3/dist-packages/PyQt4/ venv/lib/python3.4/site-packages/

# install pyacq to virtual env
python setup.py develop
