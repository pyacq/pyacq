# -*- coding: utf-8 -*-
# Copyright (c) 2016, French National Center for Scientific Research (CNRS)
# Distributed under the (new) BSD License. See LICENSE for more info.

import time
import ctypes
import os
import sys
from urllib.request import urlretrieve
import inspect
import zipfile
import shutil

import numpy as np

try:
    import clr
    from System.Reflection import Assembly
    from System import Array
    from System.Runtime.InteropServices import GCHandle, GCHandleType
    HAVE_PYTHONNET = True
except ImportError:
    HAVE_PYTHONNET = False

from ..core import Node, register_node_type, OutputStream
from pyqtgraph.Qt import QtCore, QtGui
from pyqtgraph.util.mutex import Mutex





class MultiChannelSystemW2100(Node):
    """
    Node to grab data from MultiChannelSytem W2100.
    
    
    It should be easy to modify this class to grab more channels.
    
    This is based on the McsUsbNet.ddl downloadable here:
    https://www.multichannelsystems.com/software/mcsusbnetdll
    
    This DDL is written in C#. So this code works with `pythonnet
    <https://github.com/pythonnet/pythonnet>`_ a bridge between python and
    .NET CLR

    The channel map of W2100 system is the following:
        176 channels comes from:
           4 Headstages each:
              32 channels per headstage
              1 STG sideband channel per headstage
              1 quality channel per headstage
              6 for the gyroscope/accelerometer sensor
              2 for opto STG current measurment
              = 42
           = 168
           8 IF analog channels
        = 176
        1 Digital Channel (enabled by EnableDigitalIn)
        4 Checksum Channels (enabled by EnableChecksum) (2 Magic Words and 2 Counter Words)
        4 Timestamp Channels (enabled by EnableTimestamp) (4 Counter Words)
        
    This node support grabe only:
      * 32 channels from one wireless headstage
      * 8 IF analog channels
      * 1 digital channels (16 wire)
    
    
    The range for headstage is +/- 12.5uV with int16.
    The range for IF board analogsignal is +/-2.5V
    
    """
    _output_specs = {} # outputs depend on configure
    
    def __init__(self, **kargs):
        Node.__init__(self, **kargs)
        assert HAVE_PYTHONNET, 'You must install pythonnet modules'

    def _configure(self, dll_path=None, sample_rate=10000.,
                    heastage_channel_selection=True, ifb_channel_selection=True, 
                    use_digital_channel=True,):
        '''
        Parameters
        ----------
        dll_path: str or None
            path to McsUsbNet dll. If None given try to download directly from MCS.
        sample_rate: float
            Sample rate in Hz. The system support few of them depending the channel number.
            (1000, 2000, 10000, 20000) see MCS documentation.
        heastage_channel_selection: np.array of bool of shape 32
            Selection of channels from headstage. If scalar True all channel are selected.
        ifb_channel_selection: np.array of bool of shape 8
            Selection of channels from IF board. If scalar True all channel are selected.
        use_digital_channel: bool
            Grab digital channel or not. If True a new output is created
        '''
        
        
        self.sample_rate = sample_rate
        if isinstance(heastage_channel_selection, bool):
            heastage_channel_selection = np.array([heastage_channel_selection]*32, dtype='bool')
        self.heastage_channel_selection = heastage_channel_selection
        if isinstance(ifb_channel_selection, bool):
            ifb_channel_selection = np.array([ifb_channel_selection]*8, dtype='bool')
        self.ifb_channel_selection = ifb_channel_selection
        self.use_digital_channel = use_digital_channel
        
        if dll_path is None:
            dll_path= download_dll()
            assert dll_path is not None, 'Impossible to download McsUsbNet.dll'
        
        dll = Assembly.LoadFile(dll_path)
        clr.AddReference("Mcs")
        import Mcs.Usb
        
        devicelist = Mcs.Usb.CMcsUsbListNet()
        devicelist.Initialize(Mcs.Usb.DeviceEnumNet.MCS_MEA_DEVICE)
        assert devicelist.GetNumberOfDevices() ==1, 'MCS device not found or several device'
        self.device = Mcs.Usb.CMeaDeviceNet(Mcs.Usb.McsBusTypeEnumNet.MCS_USB_BUS)
        
        # Connect to device
        status = self.device.Connect(devicelist.GetUsbListEntry(0))
        assert status ==0, 'Impossible to Connect to device'
        
        info = Mcs.Usb.CMcsUsbDacqNet.CHWInfo(self.device)
        
        # get channel info
        status, nb_adc_channel = info. GetNumberOfHWADCChannels(0)
        status, nb_digit_channel = info. GetNumberOfHWDigitalChannels(0)
        
        status = self.device.SetNumberOfChannels(nb_adc_channel, 0)

        self.device.EnableChecksum(False, 0)
        self.device. EnableDigitalIn(self.use_digital_channel, 0)
        self.device. EnableTimestamp(False, 0)

        status, analogchannels, digitalchannels, checksumchannels,\
                    timestampchannels,channelsinblock = self.device.GetChannelLayout(0, 0, 0, 0, 0, 0)
        
        self.device.SetSampleRate(int(self.sample_rate), 1, 0)
        sr = self.device.GetSampleRate(0)
        assert self.sample_rate==sr, 'Setting sample rate error'
        
        # recommended by MCS maybe we can go lower
        self.chunk_duration = 0.1 # 100ms
        self.chunksize = int(self.sample_rate * self.chunk_duration)
        
        # select 32 channel form headstage and 8 from IF board
        selected_channel = np.zeros(channelsinblock, dtype='bool')
        selected_channel[:32] = self.heastage_channel_selection # 32 channel on headstage
        selected_channel[168:176] = self.ifb_channel_selection # analogsignal on FB board
        selected_channel[176] = self.use_digital_channel

        selChannels = Array[bool](selected_channel.tolist())
        self.device.SetSelectedData(selChannels, 10 * self.chunksize, self.chunksize, 
                                Mcs.Usb.SampleSizeNet.SampleSize16Unsigned, channelsinblock)
        
        # select th first headstage if not yet selected
        self.func_w2100 = Mcs.Usb.CW2100_FunctionNet(self.device)
        self.func_w2100.SetMultiHeadstageMode(False)
        headstagestate = self.func_w2100.GetSelectedHeadstageState(0)
        headstages = self.func_w2100.GetAvailableHeadstages(30)
        if headstagestate.IdType.ID == 0xFFFF:
            if len(headstages)>0:
                self.func_w2100.SelectHeadstage(headstages[0].ID, 0)
        
        # Setup output stream  split into 3 streams (headstage/if_board/digital)
        #~ self.nb_channel = int(np.sum(selected_channel))
        self.nb_headstage_channel = np.sum(self.heastage_channel_selection)
        self.nb_ifb_channel = np.sum(self.ifb_channel_selection)
        
        self.channel_map = []
        n = 0
        if self.nb_headstage_channel>0:
            name='signals_headstage'
            output = OutputStream(spec={}, node=self, name=name)
            self.outputs[name] = output
            output.spec['shape'] = (-1, self.nb_headstage_channel)
            output.spec['sample_rate'] = self.sample_rate
            output.spec['nb_channel'] = self.nb_headstage_channel
            output.spec['dtype'] = 'float32'
            output.spec['streamtype'] = 'analogsignal'
            gain = 12.5 / 2**15 # gain to uV
            self.channel_map.append((name, slice(n, n+self.nb_headstage_channel), np.dtype('float32'), gain))
            n += self.nb_headstage_channel
        
        if self.nb_ifb_channel>0:
            name='signals_ifb'
            output = OutputStream(spec={}, node=self, name=name)
            self.outputs[name] = output
            output.spec['shape'] = (-1, self.nb_ifb_channel)
            output.spec['sample_rate'] = self.sample_rate
            output.spec['nb_channel'] = self.nb_ifb_channel
            output.spec['dtype'] = 'float32'
            output.spec['streamtype'] = 'analogsignal'
            gain = 2.5 / 2**15 # gain to V
            self.channel_map.append((name, slice(n, n+self.nb_ifb_channel), np.dtype('float32'), gain))
            n += self.nb_ifb_channel
        
        if self.use_digital_channel:
            name='digital'
            output = OutputStream(spec={}, node=self, name=name)
            self.outputs[name] = output
            output.spec['shape'] = (-1, 1)
            output.spec['sample_rate'] = self.sample_rate
            output.spec['nb_channel'] = 16
            output.spec['dtype'] = 'int16'
            output.spec['streamtype'] = 'digitalsignal'
            gain = None
            self.channel_map.append((name, slice(n, n+1), np.dtype('uint16'), gain))
            n += 1
        
        self.nb_total_channel = n
        

    def _initialize(self):
        self._thread = McsW2100_Thread(self.outputs, self.device, 
                        self.chunk_duration, self.channel_map, 
                        self.nb_total_channel, parent=self)

    def _start(self):
        # stop in case in was already running
        self.device.StopDacq()
        self.func_w2100.SetHeadstageSamplingActive(False, 0)
        
        self.func_w2100.SetHeadstageSamplingActive(True, 0)
        self.device.StartDacq()
        
        self._thread.start()

    def _stop(self):
        self._thread.stop()
        self._thread.wait()

        self.device.StopDacq()
        self.func_w2100.SetHeadstageSamplingActive(False, 0)

    def _close(self):
        pass


mcsusbnet_url = 'http://download.multichannelsystems.com/download_data/software/McsNetUsb/McsUsbNet_3.2.45.zip'


def download_dll():
    localdir = os.path.dirname(os.path.abspath(__file__))
    localfile = os.path.join(localdir, 'McsUsbNet.zip')
    if not os.path.exists(localfile):
        urlretrieve(mcsusbnet_url, localfile)
    
    try:
        dll_path = os.path.join(localdir, 'McsUsbNet.dll')
        if not os.path.exists(dll_path):
            with zipfile.ZipFile(localfile, 'r') as z:
                z.extract('McsUsbNetPackage/x64/McsUsbNet.dll', path=localdir)
            # move to localdir
            shutil.move(os.path.join(localdir,'McsUsbNetPackage/x64/McsUsbNet.dll'),
                            os.path.join(localdir,'McsUsbNet.dll'))
            shutil.rmtree(os.path.join(localdir,'McsUsbNetPackage'))
    except:
        dll_path = None
    
    return dll_path

class McsW2100_Thread(QtCore.QThread):
    def __init__(self, outputs, device, chunk_duration, channel_map, 
                            nb_total_channel, parent=None):
        QtCore.QThread.__init__(self) # parent
        self.outputs = outputs
        self.device = device
        self.chunk_duration = chunk_duration
        self.channel_map = channel_map
        self.nb_total_channel = nb_total_channel
        
        self.lock = Mutex()
        self.running = False

    def run(self):
        with self.lock:
            self.running = True

        dt = np.dtype('float32')

        head = 0
        while True:
            with self.lock:
                    if not self.running:
                        break
            
            nb_available = self.device.ChannelBlock_AvailFrames(0)
            if nb_available == 0:
                # sleep half the channelblocksize duration 0.1 second
                time.sleep(self.chunk_duration/2.)
            else:
                raw_data, nb_read = self.device.ChannelBlock_ReadFramesDictI16(0, nb_available, 0)
                # raw_data is a dict with one key
                raw_data = raw_data[0]
                
                # convert the System.Array to numpy.array
                src_hndl = GCHandle.Alloc(raw_data, GCHandleType.Pinned)
                try:
                    src_ptr = src_hndl.AddrOfPinnedObject().ToInt64()
                    np_data = np.fromstring(ctypes.string_at(src_ptr, len(raw_data)*2), dtype='uint16')
                except:
                    break
                    # TODO something clean
                finally:
                    if src_hndl.IsAllocated:
                        src_hndl.Free()
                
                all_sigs = np_data.reshape(-1, self.nb_total_channel)#.astype(dt)
                head += all_sigs.shape[0]
                for name, slice_, dtype, gain in self.channel_map:
                    sigs = all_sigs[:, slice_].astype(dtype)
                    if gain is not None:
                        sigs = (sigs - 2**15) * gain
                    self.outputs[name].send(sigs, index=head)
    
    def stop(self):
        with self.lock:
            self.running = False


register_node_type(MultiChannelSystemW2100)
