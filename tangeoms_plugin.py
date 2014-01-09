# -*- coding: utf-8 -*-
"""
Created on Wed Nov 20 14:44:32 2013

@author: anna
"""
import threading
import wx
import subprocess
import os
import numpy as np

import wx.lib.newevent
from import_xyz import import_scan_rinxyz

updateGUIEvt, EVT_UPDATE_GUI = wx.lib.newevent.NewCommandEvent()


class TangeomsPlugin(wx.Dialog):
    def __init__(self, giface, parent):
        wx.Dialog.__init__(self, parent)
        self.giface=giface
        self.parent=parent
        mainSizer = wx.BoxSizer(wx.VERTICAL)
        mainSizer.Add(wx.StaticText(self, label="Press start to start"),
                      proportion=0, flag=wx.EXPAND | wx.ALL, border=5)
        btnStart = wx.Button(self, label="Start")
        btnStop = wx.Button(self, label="Stop")
        btnClose = wx.Button(self, label="Close")

        btnStart.Bind(wx.EVT_BUTTON, lambda evt: self.Start())
        btnStop.Bind(wx.EVT_BUTTON, lambda evt: self.Stop())
        btnClose.Bind(wx.EVT_BUTTON, self.OnClose)
        self.Bind(wx.EVT_CLOSE, self.OnClose)
        self.Bind(EVT_UPDATE_GUI, self.OnUpdate)

        btnSizer = wx.BoxSizer(wx.HORIZONTAL)
        btnSizer.Add(btnStart, proportion=0, flag=wx.ALL, border=2)
        btnSizer.Add(btnStop, proportion=0, flag=wx.ALL, border=2)
        btnSizer.Add(btnClose, proportion=0, flag=wx.ALL, border=2)
        mainSizer.Add(btnSizer, proportion=0, flag=wx.EXPAND | wx.ALL, border=5)

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
        self.giface.updateMap()


class TangeomsImportPlugin(TangeomsPlugin):
    def __init__(self, giface, guiparent,  elev_real, scan, diff, scanFile, minZ, maxZ, calib=None):
        TangeomsPlugin.__init__(self, giface, guiparent)
        self.elevation=elev_real
        self.diff = diff
        self.output = scan
        self.tmp_file = scanFile
        self.minZ = minZ
        self.maxZ = maxZ
        self.calib_matrix = np.load(r"C:\Users\akratoc\TanGeoMS\output\calib_matrix.npy")
        self.threadI = None
        self.stopEvt = None
        

    def CreateThread(self):
        self.stopEvt = threading.Event()
        self.threadI = threading.Thread(target=runImport, args=[self, self.tmp_file, self.elevation,
                                                                self.output, self.diff, self.calib_matrix, self.stopEvt])

    def Start(self):
        if not self.threadI or not self.threadI.isAlive():
            kinectApp = r"C:\Users\akratoc\TanGeoMS\KinectExample3\KinectFusionExplorer-D2D\Debug\KinectFusionExplorer-D2D.exe"
            subprocess.Popen([kinectApp, self.tmp_file, '5'] )
            self.CreateThread()
            self.threadI.start()

    def Stop(self):
        subprocess.call(['taskkill', '/f', '/im', 'KinectFusionExplorer-D2D.exe'])
        if self.threadI and self.threadI.isAlive():
            self.stopEvt.set()

def runImport(guiParent, fileName, elevation, scan, diff, calib_matrix, stopEvent):
    lockFilePath = os.path.join(os.path.dirname(fileName),'lock')
    lastTime = os.path.getmtime(fileName)
    currTime = 0
    os.environ['GRASS_MESSAGE_FORMAT'] = 'standard'

    while not stopEvent.is_set():
        if not os.path.exists(lockFilePath):
            currTime = os.path.getmtime(fileName)
            if currTime == lastTime:
                continue
            lastTime = currTime
            print 'RUNNING IMPORT'
            import_scan_rinxyz(input_file=fileName, real_elev=elevation, output_elev=scan, output_diff=diff,
                               mm_resolution=0.001, calib_matrix=calib_matrix, table_mm=5, zexag=3.5)
            print 'IMPORT END'
            evt = updateGUIEvt(guiParent.GetId())
            wx.PostEvent(guiParent, evt)


def run(giface, guiparent):
    dlg = TangeomsImportPlugin(giface, guiparent, elev_real='elevation', scan='scanned', diff='diff',
                scanFile=r"C:\Users\akratoc\TanGeoMS\output\scan.txt", minZ=0.4, maxZ=0.55,
                calib='calibration')
    dlg.CenterOnParent()
    dlg.Show()


if __name__ == '__main__':
    run(None, None)