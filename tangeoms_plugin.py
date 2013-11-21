# -*- coding: utf-8 -*-
"""
Created on Wed Nov 20 14:44:32 2013

@author: anna
"""
import threading
import wx
import subprocess
import os

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

        self.stopEvt = threading.Event()

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
        self.calibRaster = calib
        self.threadK = threading.Thread(target=runKinect, args=[self.tmp_file, self.stopEvt, self.minZ, self.maxZ])
        self.threadI = threading.Thread(target=runImport, args=[self, self.tmp_file, self.elevation,
                                                                self.output, self.diff, self.calibRaster, self.stopEvt])
        
    def Start(self):
        if not self.threadK.isAlive():
            self.threadK.start()
        if not self.threadI.isAlive():
            self.threadI.start()

    def Stop(self):
        if self.threadK.isAlive():
            self.stopEvt.set()
        if self.threadI.isAlive():
            self.stopEvt.set()
    
def runKinect(fileName, stopEvent, minZ, maxZ):
    while not stopEvent.is_set():
        print 'RUNNING KINECT'
        subprocess.call([r"C:\Users\akratoc\TanGeoMS\Basic\new4\KinectFusionBasics-D2D\Debug\KinectFusionBasics-D2D.exe", fileName, '20', str(minZ), str(maxZ)])
        #subprocess.call([r"C:\Users\akratoc\TanGeoMS\Basic\new4\KinectFusionBasics-D2D\Debug\KinectFusionBasics-D2D.exe", fileName, '30', '0.5', '1.2'])
        print 'KINECT END'

def runImport(guiParent, fileName, elevation, scan, diff, calibRaster, stopEvent):
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
            import_scan_rinxyz(input_file=fileName, real_elev=elevation, output_elev=scan, output_diff=diff, mm_resolution=0.002, calib_raster=calibRaster)
            print 'IMPORT END'
            evt = updateGUIEvt(guiParent.GetId())
            wx.PostEvent(guiParent, evt)


def run(giface, guiparent):
    dlg = TangeomsImportPlugin(giface, guiparent, elev_real='elevation', scan='scanned', diff='diff',
                scanFile=r"C:\Users\akratoc\TanGeoMS\output\scan.txt", minZ=0.4, maxZ=0.55,
                calib='calibration')
    dlg.Show()


if __name__ == '__main__':
    run(None, None)