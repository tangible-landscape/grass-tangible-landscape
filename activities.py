# -*- coding: utf-8 -*-
"""
@brief activities

This program is free software under the GNU General Public License
(>=v2). Read the file COPYING that comes with GRASS for details.

@author: Anna Petrasova (akratoc@ncsu.edu)
"""
import os
import imp
import datetime
import json
import time
import traceback
import wx
import wx.lib.newevent
import wx.lib.filebrowsebutton as filebrowse

from grass.exceptions import CalledModuleError, ScriptError
from grass.pydispatch.signal import Signal

from tangible_utils import get_environment
try:
    from activities_profile import ProfileFrame
except ImportError:
    ProfileFrame = None

from activities_dashboard import DashboardFrame, MultipleDashboardFrame

# lazy importing activities_slides

updateProfile, EVT_UPDATE_PROFILE = wx.lib.newevent.NewEvent()
updateDisplay, EVT_UPDATE_DISPLAY = wx.lib.newevent.NewEvent()


class ActivitiesPanel(wx.Panel):
    def __init__(self, parent, giface, settings, scaniface):
        wx.Panel.__init__(self, parent)
        self.group = None
        self.env = None
        self.giface = giface
        self.parent = parent
        self.settings = settings
        self.scaniface = scaniface
        self.current = 0
        self.currentSubtask = 0
        self.startTime = 0
        self.endTime = 0
        self.settingsChanged = Signal('ActivitiesPanel.settingsChanged')
        self.configFile = ''
        self.tasks = []
        self.configuration = {}
        self.profileFrame = None
        self.dashboardFrame = None
        self.handsoff = None
        self.slides = None
        self.scaniface.additionalParams4Analyses = {'subTask': self.currentSubtask}
        self._processingSubTask = False

        # we want to start in pause mode to not capture any data
        self.scaniface.pause = True
        if 'activities' not in self.settings:
            self.settings['activities'] = {}
            self.settings['activities']['config'] = ''
        else:
            self.configFile = self.settings['activities']['config']

        self.configPath = filebrowse.FileBrowseButton(self, labelText='Configuration:', fileMask = "JSON file (*.json)|*.json",
                                                     changeCallback=self._loadConfiguration)
        self.configPath.SetValue(self.configFile, 0)

        self.title = wx.StaticText(self, label='')
        self.title.SetFont(wx.Font(18, wx.DEFAULT, wx.NORMAL, wx.BOLD))
        self.buttonBack = wx.Button(self, label='  <  ')
        self.buttonForward = wx.Button(self, label='  >  ')
        self.buttonBack.Bind(wx.EVT_BUTTON, self.OnBack)
        self.buttonForward.Bind(wx.EVT_BUTTON, self.OnForward)
        self.buttonStart = wx.Button(self, label='Start activity')
        self.buttonCalibrate = wx.Button(self, size=(150, -1), label='Calibrate')
        self.buttonStop = wx.Button(self, label='End activity')
        self.buttonStart.Bind(wx.EVT_BUTTON, self.OnStart)
        self.buttonCalibrate.Bind(wx.EVT_BUTTON, self.OnCalibrate)
        self.buttonStop.Bind(wx.EVT_BUTTON, self.OnStop)
        self.timeText = wx.StaticText(self, label='00:00', style=wx.ALIGN_CENTRE)
        self.timeText.SetFont(wx.Font(15, wx.FONTFAMILY_TELETYPE, wx.NORMAL, wx.FONTWEIGHT_BOLD))
        self.slidesStatus = wx.StaticText(self, label='Slides off', style=wx.ALIGN_CENTRE | wx.ALIGN_CENTRE_HORIZONTAL)
        self.slidesStatus.SetFont(wx.Font(16, wx.DEFAULT, wx.NORMAL, wx.NORMAL))

        self.buttonNext = wx.Button(self, label='Next')
        self.buttonNext.Bind(wx.EVT_BUTTON, self.OnSubtask)

        self.timer = wx.Timer(self)
        self.Bind(wx.EVT_TIMER, self.OnTimer)

        self.mainSizer = wx.BoxSizer(wx.VERTICAL)
        sizer = wx.BoxSizer(wx.HORIZONTAL)
        sizer.Add(self.configPath, proportion=1, flag=wx.EXPAND | wx.ALIGN_CENTER_VERTICAL, border=5)
        self.mainSizer.Add(sizer, flag=wx.EXPAND | wx.ALL, border=5)
        sizer = wx.BoxSizer(wx.HORIZONTAL)
        sizer.Add(self.title, proportion=1, flag=wx.EXPAND | wx.ALIGN_CENTER_VERTICAL, border=5)
        sizer.Add(self.buttonBack, proportion=0, flag=wx.EXPAND | wx.ALIGN_CENTER_VERTICAL, border=5)
        sizer.Add(self.buttonForward, proportion=0, flag=wx.EXPAND | wx.ALIGN_CENTER_VERTICAL, border=5)
        self.mainSizer.Add(sizer, flag=wx.EXPAND | wx.ALL, border=5)
        sizer = wx.BoxSizer(wx.HORIZONTAL)
        sizer.Add(self.buttonCalibrate, proportion=0, flag=wx.EXPAND | wx.ALIGN_CENTER_VERTICAL, border=5)
        self.mainSizer.Add(sizer, flag=wx.EXPAND | wx.ALL, border=5)
        sizer = wx.BoxSizer(wx.HORIZONTAL)
        sizer.Add(self.buttonStart, proportion=1, flag=wx.EXPAND | wx.ALIGN_CENTER_VERTICAL, border=5)
#        sizer.Add(self.buttonPause, proportion=1, flag=wx.EXPAND | wx.ALIGN_CENTER_VERTICAL, border=5)
        sizer.Add(self.buttonStop, proportion=1, flag=wx.EXPAND | wx.ALIGN_CENTER_VERTICAL, border=5)
        sizer.Add(self.slidesStatus, proportion=0, flag=wx.EXPAND |wx.ALIGN_CENTER | wx.LEFT | wx.RIGHT, border=10)
        sizer.Add(self.timeText, proportion=0, flag=wx.EXPAND | wx.ALIGN_CENTER | wx.LEFT, border=5)
        self.mainSizer.Add(sizer, flag=wx.EXPAND | wx.ALL, border=5)
        sizer = wx.BoxSizer(wx.HORIZONTAL)
        sizer.Add(self.buttonNext, proportion=1, flag=wx.EXPAND | wx.ALIGN_CENTER_VERTICAL, border=5)
        self.mainSizer.Add(sizer, flag=wx.EXPAND | wx.ALL, border=5)
        self.SetSizer(self.mainSizer)
        self.mainSizer.Fit(self)
        self.buttonNext.Hide()
        self.Layout()

        self.Bind(EVT_UPDATE_PROFILE, self.OnProfileUpdate)
        self.Bind(EVT_UPDATE_DISPLAY, self.OnDisplayUpdate)

        self._init()

    def _init(self):
        if self.configFile:
            try:
                with open(self.configFile, 'r') as f:
                    self.configuration = json.load(f)
                    self.tasks = self.configuration['tasks']
                    # this should reset the analysis file only when configuration is successfully loaded
                    self.settings['analyses']['file'] = ''
            except IOError:
                self.configFile = None

        self.current = 0
        if self.tasks:
            self.title.SetLabel(self.tasks[self.current]['title'])
            self.buttonBack.Enable(False)
            self.buttonForward.Enable(True)
            self.timeText.SetLabel('00:00')
            self.slidesStatus.Show(bool('slides' in self.configuration and self.configuration['slides']))
        else:
            self._enableGUI(False)
        if self.configFile:
            self.buttonNext.Show('sublayers' in self.tasks[self.current])
            self.buttonCalibrate.Show('calibrate' in self.tasks[self.current])

        self._bindUserStop()
        self.Layout()

    def _enableGUI(self, enable):
        self.buttonBack.Enable(enable)
        self.buttonForward.Enable(enable)
        self.buttonStart.Enable(enable)
        self.buttonCalibrate.Enable(enable)
        self.buttonStop.Enable(enable)
        self.slidesStatus.Enable(enable)
        self.timeText.Enable(enable)
        self.title.Enable(enable)

    def _bindUserStop(self):
        topParent = wx.GetTopLevelParent(self)
        if "keyboard_events" in self.configuration:
            items = []
            if 'stopTask' in self.configuration['keyboard_events']:
                userStopId = wx.NewId()
                items.append((wx.ACCEL_NORMAL, self.configuration['keyboard_events']['stopTask'], userStopId))
                topParent.Bind(wx.EVT_MENU, self.OnUserStop, id=userStopId)
            if 'scanOnce' in self.configuration['keyboard_events']:
                userScanOnceId = wx.NewId()
                items.append((wx.ACCEL_NORMAL, self.configuration['keyboard_events']['scanOnce'], userScanOnceId))
                topParent.Bind(wx.EVT_MENU, self.OnScanOnce, id=userScanOnceId)
            accel_tbl = wx.AcceleratorTable(items)
            topParent.SetAcceleratorTable(accel_tbl)
            # Map displays
            for mapw in self.giface.GetAllMapDisplays():
                mapw.Bind(wx.EVT_MENU, self.OnUserStop, id=userStopId)
                mapw.SetAcceleratorTable(accel_tbl)
            # Layer Manager
            lm = self.giface.lmgr
            lm.Bind(wx.EVT_MENU, self.OnUserStop, id=userStopId)
            lm.SetAcceleratorTable(accel_tbl)

    def _checkChangeTask(self):
        if self.timer.IsRunning():
            dlg = wx.MessageDialog(self, 'Stop currently running task before changing task',
                                   'Stop task',
                                   wx.OK | wx.ICON_WARNING)
            dlg.ShowModal()
            dlg.Destroy()
            return False
        return True

    def _loadConfiguration(self, event):
        self.configFile = self.configPath.GetValue().strip()
        if self.configFile:
            self.settings['activities']['config'] = self.configFile
            self._enableGUI(True)
            with open(self.configFile, 'r') as f:
                self.configuration = json.load(f)
                self.tasks = self.configuration['tasks']
                self.title.SetLabel(self.tasks[self.current]['title'])
            self._bindUserStop()
        else:
            self.settings['activities']['config'] = ''
            self._enableGUI(False)

        self.slidesStatus.Show(bool('slides' in self.configuration and self.configuration['slides']))
        self.Layout()

    def OnCalibrate(self, event):
        self._loadConfiguration(None)
        self.settings['scan']['elevation'] = self.tasks[self.current]['base']
        self.settings['output']['scan'] = 'scan_saved'
        self.settings['analyses']['file'] = ''
        if 'scanning_params' in self.tasks[self.current]:
            for each in self.tasks[self.current]['scanning_params'].keys():
                self.settings['scan'][each] = self.tasks[self.current]['scanning_params'][each]
        # resume scanning
        self.buttonCalibrate.SetLabel("Calibrating...")
        self.scaniface.filter['filter'] = False
        self._startScanning()

        wx.CallLater(2000, self.OnCalibrationDone)

    def OnCalibrationDone(self):
        self._stopScanning()
        wx.CallLater(4000, lambda: self.buttonCalibrate.SetLabel("Calibrate"))

    def OnBack(self, event):
        if not self._checkChangeTask():
            return
        # check if possible to go back
        if self.current <= 0:
            # just for sure
            self.buttonBack.Enable(False)
            return
        # move back
        self.current -= 1
        if self.current <= 0:
            self.buttonBack.Enable(False)
        self.buttonForward.Enable(True)
        if self.tasks:
            self.title.SetLabel(self.tasks[self.current]['title'])
        self.timeText.SetLabel('00:00')
        self.buttonNext.Show('sublayers' in self.tasks[self.current])
        self.buttonCalibrate.Show('calibrate' in self.tasks[self.current] and self.tasks[self.current]['calibrate'])
        self.Layout()

    def OnForward(self, event):
        if not self._checkChangeTask():
            return
        # check if possible to go forward
        if self.current >= len(self.tasks) - 1:
            # just for sure
            self.buttonForward.Enable(False)
            return
        self.current += 1
        if self.current >= len(self.tasks) - 1:
            self.buttonForward.Enable(False)
        self.buttonBack.Enable(True)
        if self.tasks:
            self.title.SetLabel(self.tasks[self.current]['title'])
        self.timeText.SetLabel('00:00')
        self.buttonNext.Show('sublayers' in self.tasks[self.current])
        self.buttonCalibrate.Show('calibrate' in self.tasks[self.current] and self.tasks[self.current]['calibrate'])
        self.Layout()

    def OnStart(self, event):
        self._loadConfiguration(None)
        if 'slides' in self.configuration and self.configuration['slides']:
            self._startSlides()
        else:
            # if no slides, start right away
            self._startTask()

    def _startSlides(self):
        # lazy import
        from activities_slides import Slides

        self.slides = Slides(self)
        self.slides.SetPosition(self.configuration['slides']['position'])
        self.slides.LoadURL('file://' + os.path.join(self.configuration['slides']['dir'], self.tasks[self.current]['slides']['file']))
        self.slides.Maximize(True)
        self.slides.Show()
        slidenum = 1
        self.slidesStatus.SetLabel("Slide {}".format(slidenum))
        for t in self.tasks[self.current]['slides']['switch']:
            slidenum += 1
            wx.CallLater(t * 1000, self._switchSlide, slidenum)
        wx.CallLater(self.tasks[self.current]['slides']['switch'][-1] * 1000, self._startTask)

    def _switchSlide(self, slidenum):
        if self.slides:  # in case it's closed prematurely
            self.slides.Next()
            self.slidesStatus.SetLabel("Slide {}".format(slidenum))

    def _startTask(self):
        self.currentSubtask = 0
        self._processingSubTask = False
        self.scaniface.additionalParams4Analyses = {'subTask': self.currentSubtask}
        self.LoadLayers()
        self.settings['scan']['elevation'] = self.tasks[self.current]['base']
        self.settings['analyses']['file'] = os.path.join(self.configuration['taskDir'], self.tasks[self.current]['analyses'])
        self.settings['output']['scan'] = 'scan'
        if 'scanning_params' in self.tasks[self.current]:
            for each in self.tasks[self.current]['scanning_params'].keys():
                self.settings['scan'][each] = self.tasks[self.current]['scanning_params'][each]
        # resume scanning
        if 'filter' in self.tasks[self.current]:
            self.scaniface.filter['filter'] = True
            self.scaniface.filter['counter'] = 0
            self.scaniface.filter['threshold'] = self.tasks[self.current]['filter']['threshold']
            self.scaniface.filter['debug'] = self.tasks[self.current]['filter']['debug']
        if 'single_scan' in self.tasks[self.current] and self.tasks[self.current]['single_scan']:
            self._stopScanning()
        else:
            self._startScanning()

        # profile
        if 'profile' in self.tasks[self.current]:
            self.StartProfile()
        # display
        if 'display' in self.tasks[self.current]:
            self.StartDisplay()

        self.startTime = datetime.datetime.now()
        self.endTime = 0
        self.timer.Start(100)

#    def OnPause(self, event):
#        pass

    def _closeAdditionalWindows(self):
        if self.slides:
            self.slides.Close()
            self.slidesStatus.SetLabel('Slides off')
        if self.profileFrame:
            self.profileFrame.Close()
            self.profileFrame = None
        if self.dashboardFrame:
            self.dashboardFrame.Destroy()
            self.dashboardFrame = None

    def _stopScanning(self):
        self.scaniface.pause = True
        self.scaniface.changedInput = True

    def _startScanning(self):
        self.scaniface.pause = False
        self.scaniface.changedInput = True

    def _removeAllLayers(self):
        ll = self.giface.GetLayerList()
        for l in reversed(ll):
            ll.DeleteLayer(l)

    def OnStop(self, event):
        self.timer.Stop()
        self._closeAdditionalWindows()
        self._removeAllLayers()
        self.settings['analyses']['file'] = ''
        self.LoadHandsOff()
        # scan after hands off
        if 'duration_handsoff' in self.configuration:
            t = self.configuration['duration_handsoff']
        else:
            t = 1
        wx.CallLater(t, self._stop)

    def _stop(self):
        # pause scanning
        self._stopScanning()
        if 'duration_handsoff_after' in self.configuration:
            t = self.configuration['duration_handsoff_after']
        else:
            t = 1
        wx.CallLater(t, self.PostProcessing)

    def OnTimer(self, event):
        diff = datetime.datetime.now() - self.startTime
        minutes = diff.seconds // 60
        seconds = diff.seconds - (minutes * 60)
        self.timeText.SetLabel('{:02d}:{:02d}'.format(minutes, seconds))
        self.endTime = diff.seconds
        if 'time_limit' in self.tasks[self.current] and \
           diff > datetime.timedelta(seconds=self.tasks[self.current]['time_limit']):
            self.timer.Stop()
            # sleep for several seconds now?
            self.OnStop(event=None)

    def LoadLayers(self):
        ll = self.giface.GetLayerList()
        zoom = []
        for i, cmd in enumerate(self.tasks[self.current]['layers']):
            opacity = 1.0
            if "layers_opacity" in self.tasks[self.current]:
                opacity = float(self.tasks[self.current]['layers_opacity'][i])
            if cmd[0] == 'd.rast':
                l = ll.AddLayer('raster', name=cmd[1].split('=')[1], checked=True,
                                opacity=opacity, cmd=cmd)
                if cmd[1].split('=')[1] != 'scan':
                    zoom.append(l.maplayer)
            elif cmd[0] == 'd.vect':
                ll.AddLayer('vector', name=cmd[1].split('=')[1], checked=True,
                            opacity=opacity, cmd=cmd)
            else:
                ll.AddLayer('command', name=' '.join(cmd), checked=True,
                            opacity=opacity, cmd=[])
        if 'sublayers' in self.tasks[self.current]:
            cmd = self.tasks[self.current]['sublayers'][0]
            if cmd[0] == 'd.rast':
                ll.AddLayer('raster', name=cmd[1].split('=')[1], checked=True,
                            opacity=1.0, cmd=cmd)
            elif cmd[0] == 'd.vect':
                ll.AddLayer('vector', name=cmd[1].split('=')[1], checked=True,
                            opacity=1.0, cmd=cmd)
        self.giface.GetMapWindow().ZoomToMap(layers=zoom)

    def LoadHandsOff(self):
        if 'handsoff' in self.configuration:
            ll = self.giface.GetLayerList()
            cmd = self.configuration['handsoff']
            self.handsoff = ll.AddLayer('command', name=' '.join(cmd), checked=True,
                                        opacity=1.0, cmd=[])

    def PostProcessing(self, onDone=None):
        wx.BeginBusyCursor()
        wx.SafeYield()
        env = get_environment(rast=self.settings['output']['scan'])
        try:
            postprocess = imp.load_source('postprocess', os.path.join(self.configuration['taskDir'], self.tasks[self.current]['analyses']))
        except StandardError as e:
            print e
            return

        functions = [func for func in dir(postprocess) if func.startswith('post_')]
        for func in functions:
            exec('del postprocess.' + func)
        try:
            postprocess = imp.load_source('postprocess', os.path.join(self.configuration['taskDir'], self.tasks[self.current]['analyses']))
        except StandardError as e:
            print e
            return
        functions = [func for func in dir(postprocess) if func.startswith('post_')]
        for func in functions:
            try:
                exec('postprocess.' + func + "(real_elev=self.settings['scan']['elevation'],"
                                             " scanned_elev=self.settings['output']['scan'],"
                                             " filterResults=self.scaniface.filter['counter'],"
                                             " timeToFinish=self.endTime,"
                                             " subTask=self.currentSubtask,"
                                             " logDir=self.configuration['logDir'],"
                                             " env=env)")
            except (CalledModuleError, StandardError, ScriptError) as e:
                traceback.print_exc()
        wx.EndBusyCursor()
        if self.handsoff:
            ll = self.giface.GetLayerList()
            ll.DeleteLayer(self.handsoff)
            self.handsoff = None

        if onDone:
            onDone()

    def StartProfile(self):
        if not ProfileFrame:
            print 'WARNING: DEM profile is not available, requires matplotlib library'
            return
        self.profileFrame = ProfileFrame(self)
        pos = self.tasks[self.current]['profile']['position']
        size = self.tasks[self.current]['profile']['size']
        self.profileFrame.SetPosition(pos)
        self.profileFrame.SetSize(size)
        self.profileFrame.set_ticks(self.tasks[self.current]['profile']['ticks'])
        self.profileFrame.set_xlim(self.tasks[self.current]['profile']['limitx'])
        self.profileFrame.set_ylim(self.tasks[self.current]['profile']['limity'])
        self.profileFrame.Show()

    def OnProfileUpdate(self, event):
        # event can be received after frame is destroyed
        if not self.profileFrame:
            return
        env = get_environment(raster=self.tasks[self.current]['profile']['raster'])
        self.profileFrame.compute_profile(points=event.points, raster=self.tasks[self.current]['profile']['raster'], env=env)

    def StartDisplay(self):
        multiple = False if 'multiple' not in self.tasks[self.current]['display'] else self.tasks[self.current]['display']['multiple']
        title = None if 'title' not in self.tasks[self.current]['display'] else self.tasks[self.current]['display']['title']
        vertical = False if 'vertical' not in self.tasks[self.current]['display'] else self.tasks[self.current]['display']['vertical']
        fontsize = self.tasks[self.current]['display']['fontsize']
        average = self.tasks[self.current]['display']['average']
        maximum = self.tasks[self.current]['display']['maximum']
        formatting_string = self.tasks[self.current]['display']['formatting_string']
        if multiple:
            self.dashboardFrame = MultipleDashboardFrame(self, fontsize=fontsize, average=average, maximum=maximum,
                                                     title=title, formatting_string=formatting_string, vertical=vertical)
        else:
            self.dashboardFrame = DashboardFrame(self, fontsize=fontsize, average=average, maximum=maximum, title=title, formatting_string=formatting_string)
        pos = self.tasks[self.current]['display']['position']
        size = self.tasks[self.current]['display']['size']
        self.dashboardFrame.SetSize(size)
        self.dashboardFrame.Show()
        self.dashboardFrame.SetPosition(pos)


    def OnDisplayUpdate(self, event):
        if not self.dashboardFrame:
            return
        self.dashboardFrame.show_value(event.value)

    def OnSubtask(self, event):
        self._processingSubTask = True
        self.LoadHandsOff()
        # keep scanning without hands
        if 'duration_handsoff' in self.configuration:
            t = self.configuration['duration_handsoff']
        else:
            t = 0
        wx.CallLater(t, self._subtaskStop)

    def _subtaskStop(self):
        # pause scanning
        self._stopScanning()
        if 'duration_handsoff_after' in self.configuration:
            t = self.configuration['duration_handsoff_after']
        else:
            t = 0
        if 'solutions' in self.tasks[self.current]:
            wx.CallLater(t, self.PostProcessing, onDone=self._showSolutions)
        else:
            wx.CallLater(t, self.PostProcessing, onDone=self._subtaskDone)

    def _showSolutions(self):
        ll = self.giface.GetLayerList()
        if self.handsoff:
            ll.DeleteLayer(self.handsoff)

        cmd = self.tasks[self.current]['solutions'][self.currentSubtask]
        if cmd[0] == 'd.rast':
            ll.AddLayer('raster', name=cmd[1].split('=')[1], checked=True,
                        opacity=1.0, cmd=cmd)
        elif cmd[0] == 'd.vect':
            ll.AddLayer('vector', name=cmd[1].split('=')[1], checked=True,
                        opacity=1.0, cmd=cmd)
        wx.CallLater(6000, self._subtaskDone)

    def _subtaskDone(self):
        # check if it was the last subTask
        if self.currentSubtask + 1 >= len(self.tasks[self.current]['sublayers']):
            # that was the last one
            self.timer.Stop()
            self._closeAdditionalWindows()
            self._removeAllLayers()
            self.settings['analyses']['file'] = ''
        else:
            # load new layers
            ll = self.giface.GetLayerList()
            for l in ll:
                if 'solutions' in self.tasks[self.current] and l.cmd == self.tasks[self.current]["solutions"][self.currentSubtask]:
                    ll.DeleteLayer(l)
                    break
            ll = self.giface.GetLayerList()
            for l in ll:
                if l.cmd == self.tasks[self.current]["sublayers"][self.currentSubtask]:
                    ll.DeleteLayer(l)
                    cmd = self.tasks[self.current]["sublayers"][self.currentSubtask + 1]
                    if cmd[0] == 'd.rast':
                        ll.AddLayer('raster', name=cmd[1].split('=')[1], checked=True,
                                    opacity=1.0, cmd=cmd)
                    elif cmd[0] == 'd.vect':
                        ll.AddLayer('vector', name=cmd[1].split('=')[1], checked=True,
                                    opacity=1.0, cmd=cmd)
                    break
            self.currentSubtask += 1
            self.scaniface.additionalParams4Analyses = {'subTask': self.currentSubtask}
            # update
            self.scaniface.filter['counter'] = 0
            for each in self.giface.GetAllMapDisplays():
                each.GetMapWindow().UpdateMap()
            self._startScanning()

            self.Raise()
            self.buttonStop.SetFocus()
        # now user can proceed to next task
        self._processingSubTask = False

    def OnUserStop(self, event):
        if self._processingSubTask:
            return
        if 'sublayers' in self.tasks[self.current]:
            self.OnSubtask(None)
        else:
            self.OnStop(None)

    def OnScanOnce(self, event):
        self.scaniface.resume_once = True
        self.scaniface.changedInput = True
