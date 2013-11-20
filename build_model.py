#-------------------------------------------------------------------------------
# Name:        module1
# Purpose:
#
# Author:      akratoc
#
# Created:     25/09/2013
# Copyright:   (c) akratoc 2013
# Licence:     <your licence>
#-------------------------------------------------------------------------------
import os
import sys
import subprocess
import threading

import wx

if __name__ == '__main__':
    WXGUIBASE = os.path.join(os.getenv('GISBASE'), 'etc', 'gui', 'wxpython')
    if WXGUIBASE not in sys.path:
        sys.path.append(WXGUIBASE)

from grass.script import core as gcore
from grass.script import raster as grast
from import_xyz import import_scan_rinxyz
from import_calib import create_calibration_raster

from mapdisp.test_mapdisp import MapdispGrassInterface
from core.render import Map
from mapdisp.frame import MapFrame
from core.globalvar import CheckWxVersion





class Test:
    def __init__(self, elev_real, scan, diff, scanFile, minZ, maxZ, calib=None):
        self.elevation=elev_real
        self.diff = diff
        self.output = scan
        self.tmp_file = scanFile
        self.minZ = minZ
        self.maxZ = maxZ
        self.calibRaster = calib

        if not CheckWxVersion([2, 9]):
            wx.InitAllImageHandlers()

        app = wx.PySimpleApp()
        map_ = Map()

        for name in (self.elevation, self.diff, 'contours'): # self.elevation,
            cmdlist = ['d.rast', 'map=%s' % name]
            if gcore.find_file(name)['fullname']:
                map_.AddLayer(ltype='raster', command=cmdlist, active=True,
                              name=name, hidden=False, opacity=1.0,
                              render=True)
                              
        for name in ('contours',):
            cmdlist = ['d.vect', 'map=%s' % name]
            if gcore.find_file(name, 'vector')['fullname']:
                map_.AddLayer(ltype='vector', command=cmdlist, active=True,
                              name=name, hidden=False, opacity=1.0,
                              render=True)
        self.giface = MapdispGrassInterface(map_=map_)
        self.frame = MapFrame(parent=None, title=_("Map display test"),
                         giface=self.giface, Map=map_)
        self.giface.mapWindow = self.frame.GetMapWindow()
        self.frame.GetMapWindow().ZoomToMap()
        self.frame.Show()
        self.frame.Bind(wx.EVT_CLOSE, self.on_close)


        self.stopEvt = threading.Event()
        threadK = threading.Thread(target=runKinect, args=[self.tmp_file, self.stopEvt, self.minZ, self.maxZ])
        threadK.start()
        threadI = threading.Thread(target=runImport, args=[self.tmp_file, self.elevation, self.output, self.diff, self.calibRaster,
                                           self.giface.GetMapWindow().UpdateMap, self.stopEvt])
        threadI.start()
        app.MainLoop()


    def on_close(self, event):
        self.stopEvt.set()
        gcore.del_temp_region()
        event.Skip()

def runKinect(fileName, stopEvent, minZ, maxZ):
    while not stopEvent.is_set():
        print 'RUNNING KINECT'
        subprocess.call([r"C:\Users\akratoc\TanGeoMS\Basic\new4\KinectFusionBasics-D2D\Debug\KinectFusionBasics-D2D.exe", fileName, '20', str(minZ), str(maxZ)])
        #subprocess.call([r"C:\Users\akratoc\TanGeoMS\Basic\new4\KinectFusionBasics-D2D\Debug\KinectFusionBasics-D2D.exe", fileName, '30', '0.5', '1.2'])
        print 'KINECT END'

def runImport(fileName, elevation, scan, diff, calibRaster, updateFunc, stopEvent):
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
            if not stopEvent.is_set():
                updateFunc()




def main():
    os.environ['GRASS_MESSAGE_FORMAT'] = 'standard'
    test = Test(elev_real='elevation', scan='scanned', diff='diff',
                scanFile=r"C:\Users\akratoc\TanGeoMS\output\scan.txt", minZ=0.4, maxZ=0.55,
                calib='calibration')





if __name__ == '__main__':
    main()