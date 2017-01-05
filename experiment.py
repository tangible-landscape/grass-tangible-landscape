# -*- coding: utf-8 -*-
"""
@brief experiment

This program is free software under the GNU General Public License
(>=v2). Read the file COPYING that comes with GRASS for details.

@author: Anna Petrasova (akratoc@ncsu.edu)
"""
import os
import imp
import datetime
import json
import wx
import wx.lib.newevent
import wx.lib.filebrowsebutton as filebrowse

from grass.exceptions import CalledModuleError, ScriptError
from grass.pydispatch.signal import Signal

from tangible_utils import get_environment
from experiment_profile import ProfileFrame

updateProfile, EVT_UPDATE_PROFILE = wx.lib.newevent.NewEvent()


class ExperimentPanel(wx.Panel):
    def __init__(self, parent, giface, settings, scaniface):
        wx.Panel.__init__(self, parent)
        self.group = None
        self.env = None
        self.giface = giface
        self.parent = parent
        self.settings = settings
        self.scaniface = scaniface
        self.current = 0
        self.startTime = 0
        self.endTime = 0
        self.settingsChanged = Signal('ExperimentPanel.settingsChanged')
        self.configFile = ''
        self.tasks = []
        self.configuration = {}
        self.profileFrame = None
        self.handsoff = None

        # we want to start in pause mode to not capture any data
        self.scaniface.pause = True
        if 'experiment' not in self.settings:
            self.settings['experiment'] = {}
            self.settings['experiment']['config'] = ''
        else:
            self.configFile = self.settings['experiment']['config']

        self.configPath = filebrowse.FileBrowseButton(self, labelText='Configuration:',
                                                     changeCallback=self._loadConfiguration)
        self.configPath.SetValue(self.configFile, 0)

        self.title = wx.StaticText(self, label='')
        self.title.SetFont(wx.Font(18, wx.DEFAULT, wx.NORMAL, wx.BOLD))
        self.buttonBack = wx.Button(self, label='  <  ')
        self.buttonForward = wx.Button(self, label='  >  ')
        self.buttonBack.Bind(wx.EVT_BUTTON, self.OnBack)
        self.buttonForward.Bind(wx.EVT_BUTTON, self.OnForward)
        self.buttonStart = wx.Button(self, label='Start task')
#        self.buttonPause = wx.Button(self, label='Pause')
        self.buttonStop = wx.Button(self, label='End task')
        self.buttonStart.Bind(wx.EVT_BUTTON, self.OnStart)
#        self.buttonPause.Bind(wx.EVT_BUTTON, self.OnPause)
        self.buttonStop.Bind(wx.EVT_BUTTON, self.OnStop)
        self.timeText = wx.StaticText(self, label='00 : 00', style=wx.ALIGN_CENTRE)
        self.timeText.SetFont(wx.Font(16, wx.DEFAULT, wx.NORMAL, wx.NORMAL))

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
        sizer.Add(self.buttonStart, proportion=1, flag=wx.EXPAND | wx.ALIGN_CENTER_VERTICAL, border=5)
#        sizer.Add(self.buttonPause, proportion=1, flag=wx.EXPAND | wx.ALIGN_CENTER_VERTICAL, border=5)
        sizer.Add(self.buttonStop, proportion=1, flag=wx.EXPAND | wx.ALIGN_CENTER_VERTICAL, border=5)
        sizer.Add(self.timeText, proportion=0, flag=wx.EXPAND | wx.ALIGN_CENTER | wx.LEFT, border=10)
        self.mainSizer.Add(sizer, flag=wx.EXPAND | wx.ALL, border=5)
        self.SetSizer(self.mainSizer)
        self.mainSizer.Fit(self)

        self.Bind(EVT_UPDATE_PROFILE, self.OnProfileUpdate)

        self._init()

    def _init(self):
        if self.configFile:
            with open(self.configFile, 'r') as f:
                self.configuration = json.load(f)
                self.tasks = self.configuration['tasks']

        self.current = 0
        self.settings['analyses']['file'] = ''
        if self.tasks:
            self.title.SetLabel(self.tasks[self.current]['title'])
        self.buttonBack.Enable(False)
        self.buttonForward.Enable(True)
        self.timeText.SetLabel('00 : 00')
        self.Layout()

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
        self.configFile = self.configPath.GetValue()
        if self.configFile:
            self.settings['experiment']['config'] = self.configFile
            with open(self.configFile, 'r') as f:
                self.configuration = json.load(f)
                self.tasks = self.configuration['tasks']
                self.title.SetLabel(self.tasks[self.current]['title'])

    def OnBack(self, event):
        if not self._checkChangeTask():
            return
        self.current -= 1
        if self.current <= 0:
            self.buttonBack.Enable(False)
        self.buttonForward.Enable(True)
        if self.tasks:
            self.title.SetLabel(self.tasks[self.current]['title'])
        self.timeText.SetLabel('00 : 00')
        self.Layout()

    def OnForward(self, event):
        if not self._checkChangeTask():
            return
        self.current += 1
        if self.current >= len(self.tasks) - 1:
            self.buttonForward.Enable(False)
        self.buttonBack.Enable(True)
        if self.tasks:
            self.title.SetLabel(self.tasks[self.current]['title'])
        self.timeText.SetLabel('00 : 00')
        self.Layout()

    def OnStart(self, event):
        self._loadConfiguration(None)
        self.LoadLayers()
        self.settings['scan']['elevation'] = self.tasks[self.current]['base']
        self.settings['analyses']['file'] = os.path.join(self.configuration['taskDir'], self.tasks[self.current]['analyses'])
        # resume scanning
        self.scaniface.filter['filter'] = True
        self.scaniface.filter['counter'] = 0
        self.scaniface.filter['threshold'] = self.tasks[self.current]['filter']['threshold']
        self.scaniface.filter['debug'] = self.tasks[self.current]['filter']['debug']
        self.scaniface.pause = False
        self.scaniface.changedInput = True

        # profile
        if 'profile' in self.tasks[self.current]:
            self.StartProfile()

        self.startTime = datetime.datetime.now()
        self.endTime = 0
        self.timer.Start(100)

#    def OnPause(self, event):
#        pass

    def OnStop(self, event):
        # pause scanning
        self.scaniface.pause = True
        self.scaniface.changedInput = True
        self.timer.Stop()
        ll = self.giface.GetLayerList()
        for l in reversed(ll):
            ll.DeleteLayer(l)
        if self.profileFrame:
            self.profileFrame.Destroy()
            self.profileFrame = None
        self.settings['analyses']['file'] = ''
        self.LoadHandsOff()
        wx.CallLater(5000, self.PostProcessing)

    def OnTimer(self, event):
        diff = datetime.datetime.now() - self.startTime
        minutes = diff.seconds // 60
        seconds = diff.seconds - (minutes * 60)
        self.timeText.SetLabel('{:02d} : {:02d}'.format(minutes, seconds))
        self.endTime = diff.seconds
        if diff > datetime.timedelta(seconds=self.tasks[self.current]['time_limit']):
            self.timer.Stop()
            # sleep for several seconds now?
            self.OnStop(event=None)

    def LoadLayers(self):
        ll = self.giface.GetLayerList()
        zoom = []
        for cmd in self.tasks[self.current]['layers']:
            if cmd[0] == 'd.rast':
                l = ll.AddLayer('raster', name=cmd[1].split('=')[1], checked=True,
                                opacity=1.0, cmd=cmd)
                zoom.append(l.maplayer)
            elif cmd[0] == 'd.vect':
                ll.AddLayer('vector', name=cmd[1].split('=')[1], checked=True,
                            opacity=1.0, cmd=cmd)
            else:
                ll.AddLayer('command', name=' '.join(cmd), checked=True,
                            opacity=1.0, cmd=[])
        self.giface.GetMapWindow().ZoomToMap(layers=zoom)

    def LoadHandsOff(self):
        ll = self.giface.GetLayerList()
        cmd = self.configuration['handsoff']
        self.handsoff = ll.AddLayer('command', name=' '.join(cmd), checked=True,
                                    opacity=1.0, cmd=[])

    def PostProcessing(self):
        wx.BeginBusyCursor()
        wx.SafeYield()
        env = get_environment(rast=self.settings['scan']['scan_name'])
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
                                             " scanned_elev=self.settings['scan']['scan_name'],"
                                             " filterResults=self.scaniface.filter['counter'],"
                                             " timeToFinish=self.endTime,"
                                             " logDir=self.configuration['logDir'],"
                                             " env=env)")
            except (CalledModuleError, StandardError, ScriptError) as e:
                print e
        wx.EndBusyCursor()
        if self.handsoff:
            ll = self.giface.GetLayerList()
            ll.DeleteLayer(self.handsoff)
            self.handsoff = None

    def StartProfile(self):
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
        env = get_environment(raster=self.tasks[self.current]['base'])
        self.profileFrame.compute_profile(points=event.points, raster=self.tasks[self.current]['base'], env=env)
        self.profileFrame.draw()
