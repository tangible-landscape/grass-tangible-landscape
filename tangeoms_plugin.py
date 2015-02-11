# -*- coding: utf-8 -*-
"""
Created on Wed Nov 20 14:44:32 2013

@author: anna
"""
import threading
import wx
import subprocess
import os
import sys
import numpy as np
from tempfile import gettempdir

import wx.lib.newevent
sys.path.append(os.path.join(os.environ['GISBASE'], "etc", "gui", "wxpython"))
from gui_core.gselect import Select

from import_xyz import import_scan
from subsurface import compute_crosssection

updateGUIEvt, EVT_UPDATE_GUI = wx.lib.newevent.NewCommandEvent()


class TangeomsPlugin(wx.Dialog):
    def __init__(self, giface, parent):
        wx.Dialog.__init__(self, parent, title="Tangeoms plugin", style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)
        self.giface=giface
        self.parent=parent
        mainSizer = wx.BoxSizer(wx.VERTICAL)
        hSizer = wx.BoxSizer(wx.HORIZONTAL)
        modelBox = wx.StaticBox(self, label="Model parameters")
        modelSizer = wx.StaticBoxSizer(modelBox, wx.VERTICAL)

        # create widgets
        btnCalibrate = wx.Button(self, label="Calibrate")
        btnStart = wx.Button(self, label="Start")
        btnStop = wx.Button(self, label="Stop")
        self.btnPause = wx.Button(self, label="Pause")
        btnClose = wx.Button(self, label="Close")
        btnScanOnce = wx.Button(self, label="Scan once")
        self.scan_name = wx.TextCtrl(self, value='scan')
        self.status = wx.StaticText(self)
        self.textInfo = wx.TextCtrl(self, size=(-1, 100), style=wx.TE_MULTILINE | wx.TE_READONLY)
        # widgets for model
        self.elevInput = Select(self, size=(-1, -1), type='rast')
        self.zexag = wx.TextCtrl(self)
        self.height = wx.TextCtrl(self)
        self.trim = {}
        for each in 'nsew':
            self.trim[each] = wx.TextCtrl(self, size=(25, -1))
        self.interpolate = wx.CheckBox(self, label="Use interpolation instead of binning")

        # layout
        hSizer.Add(btnStart, flag=wx.EXPAND | wx.ALL, border=5)
        hSizer.Add(self.btnPause, flag=wx.EXPAND | wx.ALL, border=5)
        hSizer.Add(btnStop, flag=wx.EXPAND | wx.ALL, border=5)
        hSizer.AddSpacer((40, -1))
        hSizer.Add(btnScanOnce, flag=wx.EXPAND | wx.ALL, border=5)
        mainSizer.Add(hSizer)
        hSizer = wx.BoxSizer(wx.HORIZONTAL)
        hSizer.Add(wx.StaticText(self, label="Name of scanned raster:"), flag=wx.EXPAND | wx.ALL | wx.ALIGN_CENTER_VERTICAL, border=5)
        hSizer.Add(self.scan_name, proportion=1, flag=wx.EXPAND | wx.ALL, border=5)
        mainSizer.Add(hSizer, flag=wx.EXPAND)
        hSizer = wx.BoxSizer(wx.HORIZONTAL)
        hSizer.Add(self.status, flag=wx.EXPAND | wx.ALL, border=5)
        mainSizer.Add(hSizer)
        hSizer = wx.BoxSizer(wx.HORIZONTAL)
        hSizer.Add(self.textInfo, flag=wx.EXPAND | wx.ALL, proportion=1, border=5)
        mainSizer.Add(hSizer, proportion=1, flag=wx.EXPAND)
        # model parameters
        hSizer = wx.BoxSizer(wx.HORIZONTAL)
        hSizer.Add(wx.StaticText(self, label="Reference DEM:"), flag=wx.ALL|wx.ALIGN_CENTER_VERTICAL, border=3)
        hSizer.Add(self.elevInput, proportion=1, flag=wx.ALL|wx.ALIGN_CENTER_VERTICAL, border=3)
        modelSizer.Add(hSizer, flag=wx.EXPAND)
        hSizer = wx.BoxSizer(wx.HORIZONTAL)
        hSizer.Add(wx.StaticText(self, label="Z-exaggeration:"), proportion=1, flag=wx.ALL|wx.ALIGN_CENTER_VERTICAL, border=3)
        hSizer.Add(self.zexag, flag=wx.ALL|wx.ALIGN_CENTER_VERTICAL, border=3)
        modelSizer.Add(hSizer, flag=wx.EXPAND)
        hSizer = wx.BoxSizer(wx.HORIZONTAL)
        hSizer.Add(wx.StaticText(self, label="Height above table [mm]:"), proportion=1, flag=wx.ALL|wx.ALIGN_CENTER_VERTICAL, border=3)
        hSizer.Add(self.height, flag=wx.ALL|wx.ALIGN_CENTER_VERTICAL, border=3)
        modelSizer.Add(hSizer, flag=wx.EXPAND)
        hSizer = wx.BoxSizer(wx.HORIZONTAL)
        hSizer.Add(wx.StaticText(self, label="Trim scan N, S, E, W [mm]:"), proportion=1, flag=wx.ALL|wx.ALIGN_CENTER_VERTICAL, border=3)
        for each in 'nsew':
            hSizer.Add(self.trim[each], flag=wx.ALL|wx.ALIGN_CENTER_VERTICAL, border=3)
        modelSizer.Add(hSizer, flag=wx.EXPAND)
        hSizer = wx.BoxSizer(wx.HORIZONTAL)
        hSizer.Add(self.interpolate, flag=wx.ALL|wx.ALIGN_CENTER_VERTICAL, border=3)
        modelSizer.Add(hSizer, flag=wx.EXPAND)
        mainSizer.Add(modelSizer, flag=wx.EXPAND|wx.ALL, border=5)

        hSizer = wx.BoxSizer(wx.HORIZONTAL)
        hSizer.Add(btnCalibrate, flag=wx.EXPAND | wx.ALL, border=5)
        hSizer.AddStretchSpacer()
        hSizer.Add(btnClose, flag=wx.EXPAND | wx.ALL, border=5)
        mainSizer.Add(hSizer, flag=wx.EXPAND)

        # bind events
        btnStart.Bind(wx.EVT_BUTTON, lambda evt: self.Start())
        btnStop.Bind(wx.EVT_BUTTON, lambda evt: self.Stop())
        btnClose.Bind(wx.EVT_BUTTON, self.OnClose)
        btnCalibrate.Bind(wx.EVT_BUTTON, self.Calibrate)
        btnScanOnce.Bind(wx.EVT_BUTTON, self.ScanOnce)
        self.btnPause.Bind(wx.EVT_BUTTON, lambda evt: self.Pause())
        self.Bind(wx.EVT_CLOSE, self.OnClose)
        self.Bind(EVT_UPDATE_GUI, self.OnUpdate)
        self.scan_name.Bind(wx.EVT_TEXT, self.OnScanName)
        # model parameters
        self.elevInput.Bind(wx.EVT_TEXT, self.OnModelProperties)
        self.zexag.Bind(wx.EVT_TEXT, self.OnModelProperties)
        self.height.Bind(wx.EVT_TEXT, self.OnModelProperties)
        self.interpolate.Bind(wx.EVT_CHECKBOX, self.OnModelProperties)
        for each in 'nsew':
            self.trim[each].Bind(wx.EVT_TEXT, self.OnModelProperties)

        self.SetSizer(mainSizer)
        mainSizer.Fit(self)

    def OnClose(self, event):
        self.Stop()
        self.Destroy()

    def Start(self):
        raise NotImplementedError

    def Stop(self):
        raise NotImplementedError

    def OnUpdate(self, event):
        for each in self.giface.GetAllMapDisplays():
            each.GetMapWindow().UpdateMap()
        self.UpdateText()

    def Calibrate(self, event):
        from prepare_calibration import write_matrix
        print 'REMOVE EVERYTHING FROM TABLE'
        matrix_file_path = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'calib_matrix.npy')
        write_matrix(matrix_path=matrix_file_path, min_z=0.5, max_z=1.2)


class TangeomsImportPlugin(TangeomsPlugin):
    def __init__(self, giface, guiparent,  elev_real, scan, scanFile, minZ, maxZ):
        TangeomsPlugin.__init__(self, giface, guiparent)
        self.output = scan
        self.tmp_file = scanFile
        self.minZ = minZ
        self.maxZ = maxZ
        self.data = {'scan_name': self.output, 'info_text': [],
                     'elevation': elev_real,
                     'zexag': 1., 'height': 5.,
                     'trim_nsew': [0, 0, 0, 0],
                     'interpolate': True}
        self.elevInput.SetValue(self.data['elevation'])
        self.zexag.SetValue(str(self.data['zexag']))
        self.height.SetValue(str(self.data['height']))
        self.interpolate.SetValue(self.data['interpolate'])
        for i, each in enumerate('nsew'):
            self.trim[each].SetValue(str(self.data['trim_nsew'][i]))
        self.interpolate.SetValue(self.data['interpolate'])

        calib = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'calib_matrix.npy')
        if os.path.exists(calib):
            self.calib_matrix = np.load(calib)
        else:
            self.calib_matrix = None
            giface.WriteWarning("WARNING: No calibration file exists")
        self.threadI = None
        self.stopEvt = None

    def _isRunning(self):
        ps = subprocess.Popen(['tasklist', '/fi', 'imagename eq KinectFusionExplorer-D2D.exe', '/nh'], stdout=subprocess.PIPE)
        tasks = ps.communicate()[0]
        if 'KinectFusionExplorer' in tasks:
            return True
        return False

    def ScanOnce(self, event):
        if self._isRunning():
            dlg = wx.MessageDialog(self, 'Kinect application is running, please close it first.', '',
            wx.OK | wx.ICON_EXCLAMATION)
            dlg.ShowModal()
            return
        self.status.SetLabel("Scanning...")
        wx.SafeYield()
        kinect_app = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'kinect', 'scan_once', 'KinectFusionBasics-D2D.exe')
        subprocess.call([kinect_app, self.tmp_file, '40', '0.4', '1.2', '512', '384']) # last 2 parameters must be 128/384/512 (larger for bigger models)
        self.status.SetLabel("Importing scan ...")
        import_scan(input_file=self.tmp_file,
                    real_elev=self.data['elevation'], output_elev=self.data['scan_name'], info_text=self.data['info_text'],
                    mm_resolution=0.001, calib_matrix=self.calib_matrix, trim_nsew=self.data['trim_nsew'],
                    table_mm=self.data['height'], zexag=self.data['zexag'], interpolate=self.data['interpolate'])
        self.status.SetLabel("Done.")
        self.OnUpdate(None)

    def OnScanName(self, event):
        name = self.scan_name.GetValue()
        self.data['scan_name'] = name

    def OnModelProperties(self, event):
        try:
            self.data['elevation'] = self.elevInput.GetValue()
            self.data['zexag'] = float(self.zexag.GetValue())
            self.data['height'] = float(self.height.GetValue())
            for i, each in enumerate('nsew'):
                self.data['trim_nsew'][i] = float(self.trim[each].GetValue())
            self.data['interpolate'] = self.interpolate.IsChecked()
        except ValueError:
            pass

    def UpdateText(self):
        self.textInfo.SetValue(os.linesep.join(self.data['info_text']))
        del self.data['info_text'][:]

    def CreateThread(self):
        self.stopEvt = threading.Event()
        self.threadI = threading.Thread(target=runImport, args=[self, self.tmp_file, self.data,
                                                                self.calib_matrix, self.stopEvt])

    def Start(self):
        if not self.threadI or not self.threadI.isAlive():
            kinectApp = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'kinect', 'scan_cont', 'KinectFusionExplorer-D2D.exe')
            subprocess.Popen([kinectApp, self.tmp_file, '20'] )
            self.CreateThread()
            self.threadI.start()
            self.status.SetLabel("Real-time scanning is running now.")

    def Stop(self):
        if self._isRunning():
            subprocess.call(['taskkill', '/f', '/im', 'KinectFusionExplorer-D2D.exe'])
        if self.threadI and self.threadI.isAlive():
            self.stopEvt.set()
        self.status.SetLabel("Real-time scanning stopped.")

    def Pause(self):
        if self.threadI and self.threadI.isAlive():
            self.stopEvt.set()
            self.btnPause.SetLabel("Resume")
            self.status.SetLabel("Real-time scanning paused.")
        else:
            self.CreateThread()
            self.threadI.start()
            self.btnPause.SetLabel("Pause")
            self.status.SetLabel("Real-time scanning is running now.")


def runImport(guiParent, fileName, data, calib_matrix, stopEvent):
    lockFilePath = fileName + 'lock'
    if os.path.exists(fileName):
        lastTime = os.path.getmtime(fileName)
    else:
        lastTime = None
    currTime = 0
    os.environ['GRASS_MESSAGE_FORMAT'] = 'standard'

    while not stopEvent.is_set():
        if not os.path.exists(lockFilePath) and os.path.exists(fileName):
            currTime = os.path.getmtime(fileName)
            if currTime == lastTime:
                continue
            lastTime = currTime
            import_scan(input_file=fileName, real_elev=data['elevation'], output_elev=data['scan_name'], info_text=data['info_text'],
                        mm_resolution=0.001, calib_matrix=calib_matrix, trim_nsew=data['trim_nsew'],
                        table_mm=data['height'], zexag=data['zexag'], interpolate=data['interpolate'])
#            compute_crosssection(real_elev=data['elevation'], output_elev=data['scan_name'], voxel='interp_2002_08_25',
#                                 scan_file_path=fileName, calib_matrix=calib_matrix, zexag=data['zexag'],
#                                 table_mm=data['height'], trim_nsew=data['trim_nsew'], mm_resolution=0.001, info_text=data['info_text'])
            evt = updateGUIEvt(guiParent.GetId())
            wx.PostEvent(guiParent, evt)


def run(giface, guiparent):
    dlg = TangeomsImportPlugin(giface, guiparent, elev_real='elevation', scan='scan',
                scanFile=os.path.join(os.path.realpath(gettempdir()), 'kinect_scan.txt'), minZ=0.4, maxZ=1.2)
    dlg.CenterOnParent()
    dlg.Show()


if __name__ == '__main__':
    run(None, None)
