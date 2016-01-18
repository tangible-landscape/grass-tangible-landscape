# -*- coding: utf-8 -*-
"""
Created on Wed Nov 20 14:44:32 2013

@author: anna
"""

import wx
import os
import sys

from watchdog.observers import Observer
from change_handler import RasterChangeHandler

import wx.lib.newevent
sys.path.append(os.path.join(os.environ['GISBASE'], "etc", "gui", "wxpython"))
from gui_core.gselect import Select
import grass.script as gscript

#from subsurface import compute_crosssection
from run_analyses import run_analyses


updateGUIEvt, EVT_UPDATE_GUI = wx.lib.newevent.NewCommandEvent()


class TangibleLandscapePlugin(wx.Dialog):
    def __init__(self, giface, parent):
        wx.Dialog.__init__(self, parent, title="Tangible Landscape", style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)
        self.giface=giface
        self.parent=parent

        self.output = 'scan'
        self.delay = 1.
        self.data = {'scan_name': self.output, 'info_text': [],
                     'elevation': '', 'region': '',
                     'zexag': 1., 'smooth': 7, 'numscans': 1,
                     'rotation_angle': 180, 'resolution': 2,
                     'trim_nsewtb': [0, 0, 0, 0, 60, 100],
                     'interpolate': False, 'trim_tolerance': 0.7}

        self.notebook = wx.Notebook(self)
        scanning_panel = wx.Panel(self.notebook)
        self.notebook.AddPage(scanning_panel, "Scanning")
        self.layout(scanning_panel)
        self.Layout()

        self.elevInput.SetValue(self.data['elevation'])
        self.zexag.SetValue(str(self.data['zexag']))
        self.rotate.SetValue(self.data['rotation_angle'])
        self.numscans.SetValue(self.data['numscans'])
        self.interpolate.SetValue(self.data['interpolate'])
        for i, each in enumerate('nsewtb'):
            self.trim[each].SetValue(str(self.data['trim_nsewtb'][i]))
        self.interpolate.SetValue(self.data['interpolate'])
        self.smooth.SetValue(str(self.data['smooth']))
        self.resolution.SetValue(str(self.data['resolution']))
        self.trim_tolerance.SetValue(str(self.data['trim_tolerance']))

        calib = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'calib_matrix.txt')
        if os.path.exists(calib):
            with open(calib, 'r') as f:
                self.calib_matrix = f.read()
        else:
            self.calib_matrix = None
            giface.WriteWarning("WARNING: No calibration file exists")

        self.process = None
        self.observer = None
        self.timer = wx.Timer(self)
        self.changedInput = False
        self.Bind(wx.EVT_TIMER, self.RestartIfNotRunning, self.timer)
        self.BindModelProperties()

    def layout(self, panel):
        mainSizer = wx.BoxSizer(wx.VERTICAL)
        hSizer = wx.BoxSizer(wx.HORIZONTAL)

        # create widgets
        btnCalibrate = wx.Button(panel, label="Calibrate")
        btnStart = wx.Button(panel, label="Start")
        btnStop = wx.Button(panel, label="Stop")
        btnClose = wx.Button(panel, label="Close")
        btnScanOnce = wx.Button(panel, label="Scan once")
        self.scan_name = wx.TextCtrl(panel, value='scan')
        self.status = wx.StaticText(panel)
        # widgets for model
        self.elevInput = Select(panel, size=(-1, -1), type='raster')
        self.regionInput = Select(panel, size=(-1, -1), type='region')
        self.zexag = wx.TextCtrl(panel)
        self.numscans = wx.SpinCtrl(panel, min=1, max=5, initial=1)
        self.rotate = wx.SpinCtrl(panel, min=0, max=360, initial=180)
        self.smooth = wx.TextCtrl(panel)
        self.resolution = wx.TextCtrl(panel)
        self.trim = {}
        for each in 'nsewtb':
            self.trim[each] = wx.TextCtrl(panel, size=(35, -1))
        self.trim_tolerance = wx.TextCtrl(panel)
        self.interpolate = wx.CheckBox(panel, label="Use interpolation instead of binning")

        # layout
        hSizer.Add(btnStart, flag=wx.EXPAND | wx.ALL, border=5)
        hSizer.Add(btnStop, flag=wx.EXPAND | wx.ALL, border=5)
        hSizer.AddStretchSpacer()
        hSizer.Add(btnScanOnce, flag=wx.EXPAND | wx.ALL, border=5)
        mainSizer.Add(hSizer, flag=wx.EXPAND)
        hSizer = wx.BoxSizer(wx.HORIZONTAL)
        hSizer.Add(wx.StaticText(panel, label="Name of scanned raster:"), flag=wx.EXPAND | wx.ALL | wx.ALIGN_CENTER_VERTICAL, border=5)
        hSizer.Add(self.scan_name, proportion=1, flag=wx.EXPAND | wx.ALL, border=5)
        mainSizer.Add(hSizer, flag=wx.EXPAND)
        hSizer = wx.BoxSizer(wx.HORIZONTAL)
        hSizer.Add(self.status, flag=wx.EXPAND | wx.ALL, border=5)
        mainSizer.Add(hSizer)
        # model parameters
        hSizer = wx.BoxSizer(wx.HORIZONTAL)
        hSizer.Add(wx.StaticText(panel, label="Reference DEM:"), flag=wx.ALL|wx.ALIGN_CENTER_VERTICAL, border=3)
        hSizer.Add(self.elevInput, proportion=1, flag=wx.ALL|wx.ALIGN_CENTER_VERTICAL, border=3)
        mainSizer.Add(hSizer, flag=wx.EXPAND)
        # region
        hSizer = wx.BoxSizer(wx.HORIZONTAL)
        hSizer.Add(wx.StaticText(panel, label="Reference region:"), flag=wx.ALL|wx.ALIGN_CENTER_VERTICAL, border=3)
        hSizer.Add(self.regionInput, proportion=1, flag=wx.ALL|wx.ALIGN_CENTER_VERTICAL, border=3)
        mainSizer.Add(hSizer, flag=wx.EXPAND)
        hSizer = wx.BoxSizer(wx.HORIZONTAL)
        hSizer.Add(wx.StaticText(panel, label="Z-exaggeration:"), proportion=1, flag=wx.ALL|wx.ALIGN_CENTER_VERTICAL, border=3)
        hSizer.Add(self.zexag, flag=wx.ALL|wx.ALIGN_CENTER_VERTICAL, border=3)
        mainSizer.Add(hSizer, flag=wx.EXPAND)
        # number of scans
        hSizer = wx.BoxSizer(wx.HORIZONTAL)
        hSizer.Add(wx.StaticText(panel, label="Number of scans:"), proportion=1, flag=wx.ALL|wx.ALIGN_CENTER_VERTICAL, border=3)
        hSizer.Add(self.numscans, flag=wx.ALL|wx.ALIGN_CENTER_VERTICAL, border=3)
        mainSizer.Add(hSizer, flag=wx.EXPAND)
        hSizer = wx.BoxSizer(wx.HORIZONTAL)
        hSizer.Add(wx.StaticText(panel, label="Rotation angle:"), proportion=1, flag=wx.ALL|wx.ALIGN_CENTER_VERTICAL, border=3)
        hSizer.Add(self.rotate, flag=wx.ALL|wx.ALIGN_CENTER_VERTICAL, border=3)
        mainSizer.Add(hSizer, flag=wx.EXPAND)
        # smooth
        hSizer = wx.BoxSizer(wx.HORIZONTAL)
        hSizer.Add(wx.StaticText(panel, label="Smooth value:"), proportion=1, flag=wx.ALL|wx.ALIGN_CENTER_VERTICAL, border=3)
        hSizer.Add(self.smooth, flag=wx.ALL|wx.ALIGN_CENTER_VERTICAL, border=3)
        mainSizer.Add(hSizer, flag=wx.EXPAND)
        # resolution
        hSizer = wx.BoxSizer(wx.HORIZONTAL)
        hSizer.Add(wx.StaticText(panel, label="Resolution [mm]:"), proportion=1, flag=wx.ALL|wx.ALIGN_CENTER_VERTICAL, border=3)
        hSizer.Add(self.resolution, flag=wx.ALL|wx.ALIGN_CENTER_VERTICAL, border=3)
        mainSizer.Add(hSizer, flag=wx.EXPAND)
        hSizer = wx.BoxSizer(wx.HORIZONTAL)
        hSizer.Add(wx.StaticText(panel, label="Trim scan N, S, E, W [cm]:"), proportion=1, flag=wx.ALL|wx.ALIGN_CENTER_VERTICAL, border=3)
        for each in 'nsew':
            hSizer.Add(self.trim[each], flag=wx.ALL|wx.ALIGN_CENTER_VERTICAL, border=3)
        mainSizer.Add(hSizer, flag=wx.EXPAND)
        hSizer = wx.BoxSizer(wx.HORIZONTAL)
        hSizer.Add(wx.StaticText(panel, label="Trim tolerance [0-1]:"), proportion=1, flag=wx.ALL|wx.ALIGN_CENTER_VERTICAL, border=3)
        hSizer.Add(self.trim_tolerance, flag=wx.ALL|wx.ALIGN_CENTER_VERTICAL, border=3)
        mainSizer.Add(hSizer, flag=wx.EXPAND)
        hSizer = wx.BoxSizer(wx.HORIZONTAL)
        hSizer.Add(wx.StaticText(panel, label="Limit scan vertically T, B [cm]:"), proportion=1, flag=wx.ALL|wx.ALIGN_CENTER_VERTICAL, border=3)
        for each in 'tb':
            hSizer.Add(self.trim[each], flag=wx.ALL|wx.ALIGN_CENTER_VERTICAL, border=3)
        mainSizer.Add(hSizer, flag=wx.EXPAND)
        hSizer = wx.BoxSizer(wx.HORIZONTAL)
        hSizer.Add(self.interpolate, flag=wx.ALL|wx.ALIGN_CENTER_VERTICAL, border=3)
        mainSizer.Add(hSizer, flag=wx.EXPAND)

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
        self.Bind(wx.EVT_CLOSE, self.OnClose)
        self.Bind(EVT_UPDATE_GUI, self.OnUpdate)

        panel.SetSizer(mainSizer)
        mainSizer.Fit(panel)
        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.Add(self.notebook, 1, wx.ALL | wx.EXPAND, 5)
        self.SetSizer(sizer)
        sizer.Fit(self)
        self.SetMinSize(self.GetBestSize())
        self.Layout()

    def OnClose(self, event):
        self.Stop()
        self.Destroy()

    def OnUpdate(self, event):
        for each in self.giface.GetAllMapDisplays():
            each.GetMapWindow().UpdateMap(delay=self.delay)

    def Calibrate(self, event):
        from prepare_calibration import write_matrix
        matrix_file_path = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'calib_matrix.txt')
        write_matrix(matrix_path=matrix_file_path)
        # update
        with open(matrix_file_path, 'r') as f:
            self.calib_matrix = f.read()


    def BindModelProperties(self):
        self.scan_name.Bind(wx.EVT_TEXT, self.OnScanName)
        # model parameters
        self.elevInput.Bind(wx.EVT_TEXT, self.OnModelProperties)
        self.regionInput.Bind(wx.EVT_TEXT, self.OnModelProperties)
        self.zexag.Bind(wx.EVT_TEXT, self.OnModelProperties)
        self.rotate.Bind(wx.EVT_SPINCTRL, self.OnModelProperties)
        self.rotate.Bind(wx.EVT_TEXT, self.OnModelProperties)
        self.numscans.Bind(wx.EVT_SPINCTRL, self.OnModelProperties)
        self.numscans.Bind(wx.EVT_TEXT, self.OnModelProperties)
        self.interpolate.Bind(wx.EVT_CHECKBOX, self.OnModelProperties)
        self.smooth.Bind(wx.EVT_TEXT, self.OnModelProperties)
        self.resolution.Bind(wx.EVT_TEXT, self.OnModelProperties)
        self.trim_tolerance.Bind(wx.EVT_TEXT, self.OnModelProperties)
        for each in 'nsewtb':
            self.trim[each].Bind(wx.EVT_TEXT, self.OnModelProperties)

    def ScanOnce(self, event):
        if self.process:
            return
        self.status.SetLabel("Scanning...")
        wx.SafeYield()
        params = {}
        if self.data['interpolate']:
            method = 'interpolation'
        else:
            method =  'mean'
        if self.calib_matrix:
            params['calib_matrix'] = self.calib_matrix
        if self.data['elevation']:
            params['raster'] = self.data['elevation']
        elif self.data['region']:
            params['region'] = self.data['region']
        if self.data['trim_tolerance']:
            params['trim_tolerance'] = self.data['trim_tolerance']
        trim_nsew = ','.join([str(i) for i in self.data['trim_nsewtb'][:4]])
        zrange = ','.join([str(i) for i in self.data['trim_nsewtb'][4:]])
        self.process = gscript.start_command('r.in.kinect', output=self.data['scan_name'],
                              quiet=True, trim=trim_nsew, smooth_radius=float(self.data['smooth'])/1000, method=method,
                              zrange=zrange, rotate=self.data['rotation_angle'], resolution=float(self.data['resolution'])/1000,
                              zexag=self.data['zexag'], numscan=self.data['numscans'], overwrite=True, **params)
        self.status.SetLabel("Importing scan ...")
        self.process.wait()
        self.process = None
        run_analyses(self.data['scan_name'], real_elev=self.data['elevation'], zexag=self.data['zexag'])
        self.status.SetLabel("Done.")
        self.OnUpdate(None)


    def OnScanName(self, event):
        name = self.scan_name.GetValue()
        self.data['scan_name'] = name
        if self.process and self.process.poll() is None:
            self.Stop()
            self.Start()

    def OnModelProperties(self, event):
        self.data['elevation'] = self.elevInput.GetValue()
        self.data['region'] = self.regionInput.GetValue()
        self.data['rotation_angle'] = self.rotate.GetValue()
        self.data['numscans'] = self.numscans.GetValue()
        self.data['interpolate'] = self.interpolate.IsChecked()
        self.data['smooth'] = self.smooth.GetValue()
        self.data['resolution'] = self.resolution.GetValue()
        self.data['trim_tolerance'] = self.trim_tolerance.GetValue()

        try:
            self.data['zexag'] = float(self.zexag.GetValue())
            for i, each in enumerate('nsewtb'):
                self.data['trim_nsewtb'][i] = float(self.trim[each].GetValue())
        except ValueError:
            pass
        self.changedInput = True

    def RestartIfNotRunning(self, event):
        """Mechanism to restart scanning if process ends or
        there was a change in input options"""
        if self.process and self.process.poll is not None:
            self.Start()
        if self.changedInput:
            self.changedInput = False
            self.Stop()
            self.Start()

    def Start(self):
        if self.process and self.process.poll() is None:
            return
        if self.data['interpolate']:
            method = 'interpolation'
        else:
            method =  'mean'
        params = {}
        if self.calib_matrix:
            params['calib_matrix'] = self.calib_matrix
        if self.data['elevation']:
            params['raster'] = self.data['elevation']
        elif self.data['region']:
            params['region'] = self.data['region']
        if self.data['trim_tolerance']:
            params['trim_tolerance'] = self.data['trim_tolerance']
        trim_nsew = ','.join([str(i) for i in self.data['trim_nsewtb'][:4]])
        zrange = ','.join([str(i) for i in self.data['trim_nsewtb'][4:]])
        self.process = gscript.start_command('r.in.kinect', output=self.data['scan_name'],
                              quiet=True, trim=trim_nsew, smooth_radius=float(self.data['smooth'])/1000,
                              zrange=zrange, rotate=self.data['rotation_angle'], method=method,
                              zexag=self.data['zexag'], numscan=self.data['numscans'], overwrite=True,
                              flags='l', resolution=float(self.data['resolution'])/1000, **params)
        self.status.SetLabel("Real-time scanning is running now.")
        gisenv = gscript.gisenv()
        path = os.path.join(gisenv['GISDBASE'], gisenv['LOCATION_NAME'], gisenv['MAPSET'], 'fcell')
        if not os.path.exists(path):  # this happens in new mapset
            path = os.path.join(gisenv['GISDBASE'], gisenv['LOCATION_NAME'], gisenv['MAPSET'])
        event_handler = RasterChangeHandler(self.runImport, self.data)
        self.observer = Observer()
        self.observer.schedule(event_handler, path)
        self.observer.start()
        self.timer.Start(1000)

    def Stop(self):
        if self.process and self.process.poll() is None:  # still running
            self.process.terminate()
            self.process.wait()
            self.process = None
            if self.observer:
                try:
                    self.observer.stop()
                except TypeError:  # throws error on mac
                    pass
                self.observer.join()
        self.timer.Stop()
        self.status.SetLabel("Real-time scanning stopped.")

    def runImport(self):
        run_analyses(self.data['scan_name'], real_elev=self.data['elevation'], zexag=self.data['zexag'])
        evt = updateGUIEvt(self.GetId())
        wx.PostEvent(self, evt)


def run(giface, guiparent):
    dlg = TangibleLandscapePlugin(giface, guiparent)
    dlg.CenterOnParent()
    dlg.Show()


if __name__ == '__main__':
    run(None, None)
