#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Created on Wed Nov 20 14:44:32 2013

@author: anna
"""

import os
import wx
import wx.lib.filebrowsebutton as filebrowse
from shutil import copyfile

from grass.script.utils import set_path, get_lib_path
set_path(modulename='g.gui.tangible')
from grass.script.setup import set_gui_path
set_gui_path()

from gui_core.gselect import Select
from core.settings import UserSettings
import grass.script as gscript
from grass.pydispatch.signal import Signal


from tangible_utils import run_analyses, updateGUIEvt, EVT_UPDATE_GUI
from drawing import DrawingPanel
from export import ExportPanel


class AnalysesPanel(wx.Panel):
    def __init__(self, parent, giface, settings):
        wx.Panel.__init__(self, parent)
        self.giface = giface
        self.settings = settings

        mainSizer = wx.BoxSizer(wx.VERTICAL)
        if self.settings['analyses']['file']:
            path = self.settings['analyses']['file']
            initDir = os.path.dirname(path)
        else:
            path = initDir = ""
        self.contoursSelect = Select(self, size=(-1, -1), type='vector')
        self.contoursStepTextCtrl = wx.TextCtrl(self, size=(40, -1))
        self.contoursStepTextCtrl.SetToolTipString("Contour step")

        if 'contours' in self.settings['analyses'] and self.settings['analyses']['contours']:
            self.contoursStepTextCtrl.SetValue(str(self.settings['analyses']['contours_step']))
            self.contoursSelect.SetValue(self.settings['analyses']['contours'])
        self.contoursSelect.Bind(wx.EVT_TEXT, self.OnAnalysesChange)
        self.contoursStepTextCtrl.Bind(wx.EVT_TEXT, self.OnAnalysesChange)

        self.selectAnalyses = filebrowse.FileBrowseButton(self, labelText="Analyses:",
                                                          startDirectory=initDir, initialValue=path,
                                                          changeCallback=lambda evt: self.SetAnalysesFile(evt.GetString()))
        if self.settings['analyses']['file']:
            self.selectAnalyses.SetValue(self.settings['analyses']['file'])

        newAnalyses = wx.Button(self, label="Create new file")
        newAnalyses.Bind(wx.EVT_BUTTON, lambda evt: self.CreateNewFile())

        sizer = wx.BoxSizer(wx.HORIZONTAL)
        sizer.Add(wx.StaticText(self, label="Contours:"), proportion=0, flag=wx.ALIGN_CENTER_VERTICAL|wx.RIGHT, border=5)
        sizer.Add(self.contoursSelect, proportion=1, flag=wx.ALIGN_CENTER_VERTICAL|wx.RIGHT, border=5)
        sizer.Add(self.contoursStepTextCtrl, proportion=0, flag=wx.ALIGN_CENTER_VERTICAL, border=5)
        mainSizer.Add(sizer, flag=wx.EXPAND | wx.ALL, border=5)

        sizer = wx.BoxSizer(wx.HORIZONTAL)
        sizer.Add(self.selectAnalyses, proportion=1, flag=wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, border=5)
        mainSizer.Add(sizer, flag=wx.EXPAND | wx.ALL, border=5)

        sizer = wx.BoxSizer(wx.HORIZONTAL)
        sizer.AddStretchSpacer()
        sizer.Add(newAnalyses, proportion=1, flag=wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, border=5)
        mainSizer.Add(sizer, flag=wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, border=5)

        self.SetSizer(mainSizer)
        mainSizer.Fit(self)

    def SetAnalysesFile(self, path):
        self.settings['analyses']['file'] = path

    def OnAnalysesChange(self, event):
        self.settings['analyses']['contours'] = self.contoursSelect.GetValue()
        self.settings['analyses']['contours_step'] = self.contoursStepTextCtrl.GetValue()

    def CreateNewFile(self):
        get_lib_path('g.gui.tangible')
        dlg = wx.FileDialog(self, message="Create a new file with analyses",
                            wildcard="Python source (*.py)|*.py",
                            style=wx.SAVE | wx.FD_OVERWRITE_PROMPT)
        if dlg.ShowModal() == wx.ID_OK:
            path = dlg.GetPath()
            orig = os.path.join(get_lib_path('g.gui.tangible'), 'current_analyses.py')
            if not os.path.exists(orig):
                self.giface.WriteError("File with analyses not found: {}".format(orig))
            else:
                copyfile(orig, path)
                self.selectAnalyses.SetValue(path)
                self.settings['analyses']['file'] = path
        dlg.Destroy()

class ScanningPanel(wx.Panel):
    def __init__(self, parent, giface, settings):
        wx.Panel.__init__(self, parent)
        self.giface = giface
        self.settings = settings
        self.scan = self.settings['scan']

        self.settingsChanged = Signal('ScanningPanel.settingsChanged')

        mainSizer = wx.BoxSizer(wx.VERTICAL)
        hSizer = wx.BoxSizer(wx.HORIZONTAL)

        # create widgets
        self.scan_name_ctrl = wx.TextCtrl(self, value='scan')
        # widgets for model
        self.elevInput = Select(self, size=(-1, -1), type='raster')
        self.regionInput = Select(self, size=(-1, -1), type='region')
        self.zexag = wx.TextCtrl(self)
        self.numscans = wx.SpinCtrl(self, min=1, max=5, initial=1)
        self.rotate = wx.SpinCtrl(self, min=0, max=360, initial=180)
        self.smooth = wx.TextCtrl(self)
        self.resolution = wx.TextCtrl(self)
        self.trim = {}
        for each in 'tbnsew':
            self.trim[each] = wx.TextCtrl(self, size=(40, -1))
        self.trim_tolerance = wx.TextCtrl(self)
        self.interpolate = wx.CheckBox(self, label="Use interpolation instead of binning")
        self.equalize = wx.CheckBox(self, label="Use equalized color table for scan")

        self.elevInput.SetValue(self.scan['elevation'])
        self.regionInput.SetValue(self.scan['region'])
        self.zexag.SetValue(str(self.scan['zexag']))
        self.rotate.SetValue(self.scan['rotation_angle'])
        self.numscans.SetValue(self.scan['numscans'])
        self.interpolate.SetValue(self.scan['interpolate'])
        for i, each in enumerate('nsewtb'):
            self.trim[each].SetValue(self.scan['trim_nsewtb'].split(',')[i])
        self.equalize.SetValue(self.scan['equalize'])
        self.smooth.SetValue(str(self.scan['smooth']))
        self.resolution.SetValue(str(self.scan['resolution']))
        self.trim_tolerance.SetValue(str(self.scan['trim_tolerance']))

        # layout
        mainSizer.Add(hSizer, flag=wx.EXPAND)
        hSizer = wx.BoxSizer(wx.HORIZONTAL)
        hSizer.Add(wx.StaticText(self, label="Name of scanned raster:"), flag=wx.ALL | wx.ALIGN_CENTER_VERTICAL, border=3)
        hSizer.Add(self.scan_name_ctrl, proportion=1, flag=wx.EXPAND | wx.ALL, border=5)
        mainSizer.Add(hSizer, flag=wx.EXPAND)
        # model parameters
        hSizer = wx.BoxSizer(wx.HORIZONTAL)
        hSizer.Add(wx.StaticText(self, label="Reference DEM:"), flag=wx.ALL | wx.ALIGN_CENTER_VERTICAL, border=3)
        hSizer.Add(self.elevInput, proportion=1, flag=wx.ALL | wx.ALIGN_CENTER_VERTICAL, border=3)
        mainSizer.Add(hSizer, flag=wx.EXPAND)
        # region
        hSizer = wx.BoxSizer(wx.HORIZONTAL)
        hSizer.Add(wx.StaticText(self, label="Reference region:"), flag=wx.ALL | wx.ALIGN_CENTER_VERTICAL, border=3)
        hSizer.Add(self.regionInput, proportion=1, flag=wx.ALL | wx.ALIGN_CENTER_VERTICAL, border=3)
        mainSizer.Add(hSizer, flag=wx.EXPAND)
        hSizer = wx.BoxSizer(wx.HORIZONTAL)
        hSizer.Add(wx.StaticText(self, label="Z-exaggeration:"), proportion=1, flag=wx.ALL | wx.ALIGN_CENTER_VERTICAL, border=3)
        hSizer.Add(self.zexag, flag=wx.ALL | wx.ALIGN_CENTER_VERTICAL, border=3)
        mainSizer.Add(hSizer, flag=wx.EXPAND)
        # number of scans
        hSizer = wx.BoxSizer(wx.HORIZONTAL)
        hSizer.Add(wx.StaticText(self, label="Number of scans:"), proportion=1, flag=wx.ALL | wx.ALIGN_CENTER_VERTICAL, border=3)
        hSizer.Add(self.numscans, flag=wx.ALL | wx.ALIGN_CENTER_VERTICAL, border=3)
        mainSizer.Add(hSizer, flag=wx.EXPAND)
        hSizer = wx.BoxSizer(wx.HORIZONTAL)
        hSizer.Add(wx.StaticText(self, label="Rotation angle:"), proportion=1, flag=wx.ALL | wx.ALIGN_CENTER_VERTICAL, border=3)
        hSizer.Add(self.rotate, flag=wx.ALL | wx.ALIGN_CENTER_VERTICAL, border=3)
        mainSizer.Add(hSizer, flag=wx.EXPAND)
        # smooth
        hSizer = wx.BoxSizer(wx.HORIZONTAL)
        hSizer.Add(wx.StaticText(self, label="Smooth value:"), proportion=1, flag=wx.ALL | wx.ALIGN_CENTER_VERTICAL, border=3)
        hSizer.Add(self.smooth, flag=wx.ALL | wx.ALIGN_CENTER_VERTICAL, border=3)
        mainSizer.Add(hSizer, flag=wx.EXPAND)
        # resolution
        hSizer = wx.BoxSizer(wx.HORIZONTAL)
        hSizer.Add(wx.StaticText(self, label="Resolution [mm]:"), proportion=1, flag=wx.ALL | wx.ALIGN_CENTER_VERTICAL, border=3)
        hSizer.Add(self.resolution, flag=wx.ALL | wx.ALIGN_CENTER_VERTICAL, border=3)
        mainSizer.Add(hSizer, flag=wx.EXPAND)
        hSizer = wx.BoxSizer(wx.HORIZONTAL)
        hSizer.Add(wx.StaticText(self, label="Limit scan vertically T, B [cm]:"), proportion=1, flag=wx.ALL | wx.ALIGN_CENTER_VERTICAL, border=3)
        for each in 'tb':
            hSizer.Add(self.trim[each], flag=wx.ALL | wx.ALIGN_CENTER_VERTICAL, border=3)
        mainSizer.Add(hSizer, flag=wx.EXPAND)
        hSizer = wx.BoxSizer(wx.HORIZONTAL)
        hSizer.Add(wx.StaticText(self, label="Trim scan N, S, E, W [cm]:"), proportion=1, flag=wx.ALL | wx.ALIGN_CENTER_VERTICAL, border=3)
        for each in 'nsew':
            hSizer.Add(self.trim[each], flag=wx.ALL | wx.ALIGN_CENTER_VERTICAL, border=3)
        mainSizer.Add(hSizer, flag=wx.EXPAND)
        hSizer = wx.BoxSizer(wx.HORIZONTAL)
        hSizer.Add(wx.StaticText(self, label="Trim tolerance [0-1]:"), proportion=1, flag=wx.ALL | wx.ALIGN_CENTER_VERTICAL, border=3)
        hSizer.Add(self.trim_tolerance, flag=wx.ALL | wx.ALIGN_CENTER_VERTICAL, border=3)
        mainSizer.Add(hSizer, flag=wx.EXPAND)
        hSizer = wx.BoxSizer(wx.HORIZONTAL)
        hSizer.Add(self.interpolate, flag=wx.ALL | wx.ALIGN_CENTER_VERTICAL, border=3)
        mainSizer.Add(hSizer, flag=wx.EXPAND)
        hSizer = wx.BoxSizer(wx.HORIZONTAL)
        hSizer.Add(self.equalize, flag=wx.ALL | wx.ALIGN_CENTER_VERTICAL, border=3)
        mainSizer.Add(hSizer, flag=wx.EXPAND)

        self.SetSizer(mainSizer)
        mainSizer.Fit(self)

        self.BindModelProperties()

    def BindModelProperties(self):
        self.scan_name_ctrl.Bind(wx.EVT_TEXT, self.OnModelProperties)
        # model parameters
        self.elevInput.Bind(wx.EVT_TEXT, self.OnModelProperties)
        self.regionInput.Bind(wx.EVT_TEXT, self.OnModelProperties)
        self.zexag.Bind(wx.EVT_TEXT, self.OnModelProperties)
        self.rotate.Bind(wx.EVT_SPINCTRL, self.OnModelProperties)
        self.rotate.Bind(wx.EVT_TEXT, self.OnModelProperties)
        self.numscans.Bind(wx.EVT_SPINCTRL, self.OnModelProperties)
        self.numscans.Bind(wx.EVT_TEXT, self.OnModelProperties)
        self.interpolate.Bind(wx.EVT_CHECKBOX, self.OnModelProperties)
        self.equalize.Bind(wx.EVT_CHECKBOX, self.OnModelProperties)
        self.smooth.Bind(wx.EVT_TEXT, self.OnModelProperties)
        self.resolution.Bind(wx.EVT_TEXT, self.OnModelProperties)
        self.trim_tolerance.Bind(wx.EVT_TEXT, self.OnModelProperties)
        for each in 'nsewtb':
            self.trim[each].Bind(wx.EVT_TEXT, self.OnModelProperties)

    def OnModelProperties(self, event):
        self.scan['scan_name'] = self.scan_name_ctrl.GetValue()
        self.scan['elevation'] = self.elevInput.GetValue()
        self.scan['region'] = self.regionInput.GetValue()
        self.scan['rotation_angle'] = self.rotate.GetValue()
        self.scan['numscans'] = self.numscans.GetValue()
        self.scan['interpolate'] = self.interpolate.IsChecked()
        self.scan['equalize'] = self.equalize.IsChecked()
        self.scan['smooth'] = self.smooth.GetValue()
        self.scan['resolution'] = self.resolution.GetValue()
        self.scan['trim_tolerance'] = self.trim_tolerance.GetValue()

        try:
            self.scan['zexag'] = float(self.zexag.GetValue())
            nsewtb_list = []
            for each in 'nsewtb':
                nsewtb_list.append(self.trim[each].GetValue())
            self.scan['trim_nsewtb'] = ','.join(nsewtb_list)
        except ValueError:
            pass
        self.settingsChanged.emit()


class TangibleLandscapePlugin(wx.Dialog):
    def __init__(self, giface, parent):
        wx.Dialog.__init__(self, parent, title="Tangible Landscape", style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)
        self.giface = giface
        self.parent = parent

        if not gscript.find_program('r.in.kinect'):
            self.giface.WriteError("ERROR: Module r.in.kinect not found.")

        self.settings = {}
        UserSettings.ReadSettingsFile(settings=self.settings)
        # for the first time
        if not 'tangible' in self.settings:
            self.settings['tangible'] = {'calibration': {'matrix': None},
                                         'analyses': {'file': None,
                                                      'contours': None,
                                                      'contours_step': 1},
                                         'scan': {'scan_name': 'scan',
                                                  'elevation': '', 'region': '',
                                                  'zexag': 1., 'smooth': 7, 'numscans': 1,
                                                  'rotation_angle': 180, 'resolution': 2,
                                                  'trim_nsewtb': '30,30,30,30,60,100',
                                                  'interpolate': False, 'trim_tolerance': 0.7,
                                                  'equalize': False
                                                  }
                                         }
        self.scan = self.settings['tangible']['scan']
        self.calib_matrix = self.settings['tangible']['calibration']['matrix']
        if not self.calib_matrix:
            giface.WriteWarning("WARNING: No calibration file exists")

        self.delay = 0.3
        self.process = None
        self.observer = None
        self.timer = wx.Timer(self)
        self.changedInput = False

        self.notebook = wx.Notebook(self)
        scanning_panel = ScanningPanel(self.notebook, self.giface, self.settings['tangible'])
        self.notebook.AddPage(scanning_panel, "Scanning")
        scanning_panel.settingsChanged.connect(lambda: setattr(self, 'changedInput', True))
        analyses_panel = AnalysesPanel(self.notebook, self.giface, self.settings['tangible'])
        self.notebook.AddPage(analyses_panel, "Analyses")
        self.exportPanel = ExportPanel(self.notebook, self.giface, self.settings['tangible'])
        self.notebook.AddPage(self.exportPanel, "Export")
        self.exportPanel.settingsChanged.connect(lambda: setattr(self, 'changedInput', True))
        self.drawing_panel = DrawingPanel(self.notebook, self.giface, self.settings['tangible'])
        self.notebook.AddPage(self.drawing_panel, "Drawing")
        self.drawing_panel.Bind(EVT_UPDATE_GUI, self.OnUpdate)
        self.drawing_panel.settingsChanged.connect(lambda: setattr(self, 'changedInput', True))

        btnStart = wx.Button(self, label="Start")
        btnStop = wx.Button(self, label="Stop")
        btnScanOnce = wx.Button(self, label="Scan once")
        btnCalibrate = wx.Button(self, label="Calibrate")
        btnHelp = wx.Button(self, label="Help")
        btnClose = wx.Button(self, label="Close")
        self.status = wx.StaticText(self)

        # bind events
        btnStart.Bind(wx.EVT_BUTTON, lambda evt: self.Start())
        btnStop.Bind(wx.EVT_BUTTON, lambda evt: self.Stop())
        btnCalibrate.Bind(wx.EVT_BUTTON, self.Calibrate)
        btnScanOnce.Bind(wx.EVT_BUTTON, self.ScanOnce)
        btnHelp.Bind(wx.EVT_BUTTON, self.OnHelp)
        btnClose.Bind(wx.EVT_BUTTON, self.OnClose)
        self.Layout()

        sizer = wx.BoxSizer(wx.VERTICAL)
        hSizer = wx.BoxSizer(wx.HORIZONTAL)
        hSizer.Add(btnStart, flag=wx.EXPAND | wx.ALL, border=5)
        hSizer.Add(btnStop, flag=wx.EXPAND | wx.ALL, border=5)
        hSizer.Add(btnCalibrate, flag=wx.EXPAND | wx.ALL, border=5)
        hSizer.Add(btnScanOnce, flag=wx.EXPAND | wx.ALL, border=5)
        sizer.Add(hSizer, 0, wx.ALL | wx.EXPAND, 5)
        hSizer = wx.BoxSizer(wx.HORIZONTAL)
        hSizer.Add(self.status, flag=wx.EXPAND | wx.LEFT, border=5)
        sizer.Add(hSizer)
        sizer.Add(self.notebook, 1, wx.ALL | wx.EXPAND, 5)
        hSizer = wx.BoxSizer(wx.HORIZONTAL)
        hSizer.AddStretchSpacer()
        hSizer.Add(btnHelp, flag=wx.EXPAND | wx.ALL, border=5)
        hSizer.Add(btnClose, flag=wx.EXPAND | wx.ALL, border=5)
        sizer.Add(hSizer, flag=wx.EXPAND)

        self.SetSizer(sizer)
        sizer.Fit(self)
        self.SetMinSize(self.GetBestSize())
        self.Layout()

        self.Bind(wx.EVT_TIMER, self.RestartIfNotRunning, self.timer)
        self.Bind(wx.EVT_CLOSE, self.OnClose)
        self.Bind(EVT_UPDATE_GUI, self.OnUpdate)

    def OnHelp(self, event):
        """Show help"""
        self.giface.Help(entry='g.gui.tangible', online=False)

    def OnClose(self, event):
        self.Stop()
        UserSettings.SaveToFile(self.settings)
        self.Destroy()

    def OnUpdate(self, event):
        for each in self.giface.GetAllMapDisplays():
            each.GetMapWindow().UpdateMap(delay=self.delay)

    def Calibrate(self, event):
        res = gscript.parse_command('r.in.kinect', flags='c', overwrite=True)
        if not (res['calib_matrix'] and len(res['calib_matrix'].split(',')) == 9):
            gscript.message(_("Failed to calibrate"))
            return
        self.settings['tangible']['calibration']['matrix'] = res['calib_matrix']
        UserSettings.SaveToFile(self.settings)

        # update
        self.calib_matrix = res['calib_matrix']

    def Scan(self, continuous):
        if self.process and self.process.poll() is None:
            return
        self.status.SetLabel("Scanning...")
        wx.SafeYield()
        params = {}
        if self.scan['scan_name']:
            params['output'] = self.scan['scan_name']
        if self.settings['tangible']['drawing']['active'] and self.settings['tangible']['drawing']['name']:
            params['draw_output'] = self.settings['tangible']['drawing']['name']
            params['draw'] = self.settings['tangible']['drawing']['type']
            params['draw_threshold'] = self.settings['tangible']['drawing']['threshold']
            # we don't want to scan when drawing
            del params['output']
        if self.scan['interpolate']:
            method = 'interpolation'
        else:
            method = 'mean'
        if self.calib_matrix:
            params['calib_matrix'] = self.calib_matrix
        if self.scan['elevation']:
            params['raster'] = self.scan['elevation']
        elif self.scan['region']:
            params['region'] = self.scan['region']
        if self.scan['trim_tolerance']:
            params['trim_tolerance'] = self.scan['trim_tolerance']
        trim_nsew = ','.join(self.scan['trim_nsewtb'].split(',')[:4])
        zrange = ','.join(self.scan['trim_nsewtb'].split(',')[4:])
        if continuous:
            params['flags'] = 'l'
        if self.scan['equalize'] and 'output' in params:
            if 'flags' in params and params['flags']:
                params['flags'] += 'e'
        if self.settings['tangible']['analyses']['contours'] and 'output' in params:
            params['contours'] = self.settings['tangible']['analyses']['contours']
            params['contours_step'] = self.settings['tangible']['analyses']['contours_step']
        # export PLY
        if 'export' in self.settings['tangible'] and self.settings['tangible']['export']['PLY'] and \
           self.settings['tangible']['export']['PLY_file']:
            params['ply'] = self.settings['tangible']['export']['PLY_file']
        # export color
        if 'export' in self.settings['tangible'] and self.settings['tangible']['export']['color'] and \
           self.settings['tangible']['export']['color_name']:
            params['color_output'] = self.settings['tangible']['export']['color_name']

        self.process = gscript.start_command('r.in.kinect',
                                             trim=trim_nsew, smooth_radius=float(self.scan['smooth'])/1000,
                                             method=method, zrange=zrange, rotate=self.scan['rotation_angle'],
                                             resolution=float(self.scan['resolution'])/1000,
                                             zexag=self.scan['zexag'], numscan=self.scan['numscans'],
                                             overwrite=True, quiet=True, **params)
        return self.process

    def ScanOnce(self, event):
        self.Scan(continuous=False)
        self.status.SetLabel("Importing scan...")
        self.process.wait()
        self.process = None
        run_analyses(settings=self.settings, analysesFile=self.settings['tangible']['analyses']['file'])
        self.status.SetLabel("Done.")
        self.OnUpdate(None)

    def RestartIfNotRunning(self, event):
        """Mechanism to restart scanning if process ends or
        there was a change in input options"""
        if self.process and self.process.poll() is not None:
            self.Start()
        if self.changedInput:
            self.changedInput = False
            self.Stop()
            self.Start()

    def Start(self):
        self.Scan(continuous=True)
        self.status.SetLabel("Real-time scanning is running now.")
        gisenv = gscript.gisenv()
        mapsetPath = os.path.join(gisenv['GISDBASE'], gisenv['LOCATION_NAME'], gisenv['MAPSET'])
        path1 = os.path.join(mapsetPath, 'fcell')
        path2 = os.path.join(mapsetPath, 'vector')
        if not os.path.exists(path1):  # this happens in new mapset
            paths = [mapsetPath, mapsetPath]
        else:
            paths = [path1, path2]
        handlers = [RasterChangeHandler(self.runImport, self.scan),
                    DrawingChangeHandler(self.runImportDrawing, self.settings['tangible']['drawing']['name'])]
        self.observer = Observer()
        for path, handler in zip(paths, handlers):
            self.observer.schedule(handler, path)

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
        run_analyses(settings=self.settings, analysesFile=self.settings['tangible']['analyses']['file'])
        evt = updateGUIEvt(self.GetId())
        wx.PostEvent(self, evt)

    def runImportDrawing(self):
        self.drawing_panel.appendVector()
        run_analyses(settings=self.settings, analysesFile=self.settings['tangible']['analyses']['file'])
        evt = updateGUIEvt(self.GetId())
        wx.PostEvent(self, evt)



def main(giface=None):
    global Observer, RasterChangeHandler, DrawingChangeHandler
    from watchdog.observers import Observer
    from change_handler import RasterChangeHandler, DrawingChangeHandler
    dlg = TangibleLandscapePlugin(giface, parent=None)
    dlg.Show()


if __name__ == '__main__':
    gscript.parser()
    from watchdog.observers import Observer
    from change_handler import RasterChangeHandler, DrawingChangeHandler
    main()
