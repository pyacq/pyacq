import numpy as np

from ..core import Node, register_node_type
from pyqtgraph.Qt import QtCore, QtGui


class NumpyDeviceBuffer(Node):
    """A fake acquisition device with one output stream.
    
    This node streams data from a predefined buffer in an endless loop.
    """
    _output_specs = {'output': 
                        {'compression': '', 'timeaxis': 0}}

    def __init__(self, **kargs):
        Node.__init__(self, **kargs)

    def configure(self, *args, **kwargs):
        """
        Parameters for configure
        ---
        buffer : array
            Data to send. May have any shape or dtype.
        sample_interval : float
            Time duration of a single data sample. This determines the rate at
            which data is sent.
        chunksize : int
            Length of chunks (along axis 0 of the data array) to send. The data
            shape along axis 0 must be a multiple of chunksize.
        streamtype : str
            Type of stream. See :func:`OutputStream.configure()`.
        """
        return Node.configure(self, *args, **kwargs)

    def _configure(self, buffer, sample_interval=0.001, chunksize=256,
                   streamtype='analogsignal'):
        
        assert buffer.shape[0] % chunksize == 0, 'buffer.shape[0] must be multiple of chunksize'
        
        self.buffer = buffer
        self.sample_interval = sample_interval
        self.chunksize = chunksize
        
        self.output.spec['shape'] = (-1,) + buffer.shape[1:]
        self.output.spec['dtype'] = buffer.dtype
        self.output.spec['timeaxis'] = 0
        self.output.spec['sample_rate'] = 1. / sample_interval
        self.output.spec['streamtype'] = streamtype
        self.output.configure()
    
    def _initialize(self):
        self.head = 0
        self.timer = QtCore.QTimer(singleShot=False, interval=int(self.chunksize*self.sample_interval*1000))
        self.timer.timeout.connect(self.send_data)
    
    def _start(self):
        self.timer.start()

    def _stop(self):
        self.timer.stop()
    
    def _close(self):
        pass
    
    def send_data(self):
        buf = self.buffer
        i1 = self.head % buf.shape[0]
        self.head += self.chunksize
        i2 = i1 + self.chunksize
        self.output.send(self.head, buf[i1:i2])

register_node_type(NumpyDeviceBuffer)



class FakeVideoSource(NumpyDeviceBuffer):
    """Fake video source node.
    
    Creates and configures a node that outputs a random video stream.
    """
    def __init__(self, shape=(10, 256, 256), dtype=np.ubyte, scale=30, loc=128,
                 sample_interval=0.1, chunksize=1):
        NumpyDeviceBuffer.__init__(self)
        buf = np.random.normal(size=shape, scale=scale, loc=loc).astype(dtype)
        self.configure(buffer=buf, sample_interval=sample_interval,
                       chunksize=chunksize, streamtype='image/video')

    
class FakeSpectralSource(NumpyDeviceBuffer):
    """Fake analogsignal source with spectral signal.
    
    Creates and configures a node that outputs a multi-channel analog signal
    composed of random noise and sine waves.
    
    Parameters
    ----------
    nb_channel : int or None
        Number of channels in the data. If None, then one channel is generated
        and the stream shape will be 1D.
    """
    def __init__(self, nb_channel=16, sample_interval=1e-3, chunksize=256):
        NumpyDeviceBuffer.__init__(self)
        if nb_channel is None:
            nb_channel = 1
            flatten = True
        else:
            flatten = False
        
        length = 40 * chunksize
        t = np.arange(length) * sample_interval
        buf = np.random.rand(length, nb_channel) * 0.05
        buf += np.sin(2 * np.pi * (200. + 50*np.sin(t)) * t)[:, None] * 0.5
        
        buf = buf.astype('float32')
        if flatten:
            buf = np.ravel(buf)
        
        self.configure(buffer=buf, sample_interval=sample_interval,
                       chunksize=chunksize, streamtype='analogsignal')

    
class FakeSpikeSource(NumpyDeviceBuffer):
    """Fake analogsignal source with spiking signal.
    
    Creates and configures a node that outputs a multi-channel analog signal
    composed of random noise with embedded spike trains.
    """
    def __init__(self, nb_channel=16, sample_interval=1e-4, chunksize=1024):
        NumpyDeviceBuffer.__init__(self)
        
        # todo: would be nice to make this usable for spike sorting tests
        #   * multiple cells per signal
        #   * each cell has a particular spike waveform
        #   * some cells shared between adjacent electrodes
        import scipy.ndimage
        
        if nb_channel is None:
            nb_channel = 1
            flatten = True
        else:
            flatten = False
        
        # allow multidimensional channel array
        if isinstance(nb_channel, tuple):
            channel_shape = nb_channel
        else:
            channel_shape = (nb_channel,)

        duration = 5.0
        samples = int(duration / sample_interval)
        samples = chunksize * (samples // chunksize)
        
        # generate single spike waveform
        spike = np.zeros(int(4e-3 / sample_interval))
        spike[int(1.7e-3 / sample_interval)] += 2e-3
        spike = scipy.ndimage.gaussian_filter(spike, 5)
        spike[int(1.1e-3 / sample_interval)] -= 5e-3
        spike = scipy.ndimage.gaussian_filter(spike, 3)
        spike /= -spike.min()
        
        # start all data with random noise
        buf = np.random.normal(size=(samples,) + channel_shape, loc=0, scale=1e-4)
        
        # generate spike trains
        for ind in np.ndindex(channel_shape):
            spikerate = 10.0
            isi = np.random.exponential(1./spikerate, size=spikerate*2*duration)
            spiketimes = np.cumsum(isi, axis=0)
            spikeinds = (spiketimes / sample_interval).astype(np.int)
            spikeinds = spikeinds[spikeinds < samples]
        
            spikeamps = np.random.normal(size=len(spikeinds), loc=4e-3, scale=0.5e-3)
            sl = (slice(None),) + ind  # how to select all samples in this chnnel
            buf[sl][spikeinds] += spikeamps
            buf[sl] = np.convolve(buf[sl], spike, mode='same')
            
        # add some hf noise back in
        buf += np.random.normal(size=buf.shape, loc=0, scale=1e-4)
        
        if flatten:
            buf = np.ravel(buf)
        buf = buf.astype(np.float32)
        
        self.configure(buffer=buf, sample_interval=sample_interval,
                       chunksize=chunksize)
