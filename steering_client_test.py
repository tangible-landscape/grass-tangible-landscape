# -*- coding: utf-8 -*-
"""
Created on Tue Jun 19 21:58:31 2018

@author: anna
"""

import wx
import re
import os
import json
import wx.lib.newevent

from client import SteeringClient, EVT_PROCESS_FOR_DASHBOARD_EVENT

import grass.script as gscript

updateDisplay, EVT_UPDATE_DISPLAY = wx.lib.newevent.NewEvent()

SERVER = '/home/anna/dev/grass-tangible-landscape-pops-steering/server.py'
CONFIG = '/home/anna/Documents/Projects/SOD2/POPS/SOD/config_steering.json'


class SteeringFrame(wx.Frame):
    def __init__(self, parent, title):
        wx.Frame.__init__(self, parent=parent, title=title)
        
        
        #self.socket = None
        #self.urlSteering = 'localhost:8889'
        #self.resultsToDisplay = Queue.Queue()
        with open(CONFIG, 'r') as f:
            self.configuration = json.load(f)
        panel = wx.Panel(self)

        btnStart = wx.Button(panel, label="Initialize")
        btnStop = wx.Button(panel, label="Stop")
        btnPlay = wx.Button(panel, label=u"\u25B6")
        btnPause = wx.Button(panel, label=u"\u23F8")
        btnForward = wx.Button(panel, label=u"\u23E9")
        btnBack = wx.Button(panel, label=u"\u23EA")
        btnLoad = wx.Button(panel, label="Load data")
        btnSync = wx.Button(panel, label="Sync next year")

        btnStart.Bind(wx.EVT_BUTTON, self.OnStart)
        btnStop.Bind(wx.EVT_BUTTON, self.OnStop)
        btnPlay.Bind(wx.EVT_BUTTON, self.OnPlay)
        btnPause.Bind(wx.EVT_BUTTON, self.OnPause)
        btnForward.Bind(wx.EVT_BUTTON, self.OnStepForward)
        btnBack.Bind(wx.EVT_BUTTON, self.OnStepBack)
        btnSync.Bind(wx.EVT_BUTTON, self.OnSync)
        btnLoad.Bind(wx.EVT_BUTTON, self._sendFile)
        
        self.Bind(EVT_UPDATE_DISPLAY, self._update)
        self.Bind(EVT_PROCESS_FOR_DASHBOARD_EVENT, self._uploadStepToDashboard)
        self.Bind(wx.EVT_CLOSE, self.OnClose)

        self.infoText = wx.StaticText(panel, label=''*20)
        # btnChangeInput = wx.Button(panel, label="Change input")
        
        box = wx.BoxSizer(wx.VERTICAL)
        box1 = wx.BoxSizer(wx.HORIZONTAL)
        box1.Add(btnStart, proportion=1, flag=wx.EXPAND|wx.ALL, border=2)
        box1.Add(btnStop, proportion=1, flag=wx.EXPAND|wx.ALL, border=2)
        box.Add(box1, flag=wx.EXPAND)

        box2 = wx.BoxSizer(wx.HORIZONTAL)
        box2.Add(btnBack, proportion=1, flag=wx.EXPAND|wx.ALL, border=2)
        box2.Add(btnPlay, proportion=1, flag=wx.EXPAND|wx.ALL, border=2)
        box2.Add(btnPause, proportion=1, flag=wx.EXPAND|wx.ALL, border=2)
        box2.Add(btnForward, proportion=1, flag=wx.EXPAND|wx.ALL, border=2)
        box.Add(box2, flag=wx.EXPAND)

        box3 = wx.BoxSizer(wx.HORIZONTAL)
        box3.Add(btnLoad, proportion=1, flag=wx.EXPAND|wx.ALL, border=2)
        box3.Add(btnSync, proportion=1, flag=wx.EXPAND|wx.ALL, border=2)
        box.Add(box3, flag=wx.EXPAND)

        box4 = wx.BoxSizer(wx.HORIZONTAL)
        box4.Add(self.infoText)
        box.Add(box4, flag=wx.EXPAND)

        panel.SetSizerAndFit(box)
        panel.Layout()

        self._connectSteering()

    def _sendFile(self, event):
        path = '/tmp/test.txt'
        fsize = os.path.getsize(path)
        self.socket.sendall('clientfile:{}:{}'.format(fsize, path))

    def _update(self, event):
        self.infoText.SetLabel(event.value)

    def _getPlayerName(self):
        return 'run'

    def _getEventName(self):
        return 'tmpevent'

    def _connectSteering(self):
        steer = self.configuration['POPS']['steering']
        self.steeringClient = SteeringClient(steer['url'], port_interface=steer['port_interface'],
                                             port_simulation=steer['port_simulation'],
                                             launch_server=SERVER,
                                             local_gdbase=True, log=None, eventHandler=self)
        #self.steeringClient.set_on_done(self._afterSimulation)
        #self.steeringClient.set_on_step_done(self._uploadStepToDashboard)
        self.steeringClient.set_steering(True)
        self.steeringClient.connect()

    def _uploadStepToDashboard(self, event):
        res = re.search('[0-9]{4}_[0-9]{2}_[0-9]{2}', event.name)
        date = res.group()
        text = "Computed " + date + " " + event.name
        self.infoText.SetLabel(text)

    def OnStart(self, event):
        studyArea = self.configuration['tasks'][0]['base']
        host = self.configuration['POPS']['model']['host']
        probability = self.configuration['POPS']['model']['probability_series']

        postfix = self._getEventName() + '__' + self._getPlayerName() + '_'
        probability = probability + '__' + postfix

        extent = gscript.raster_info(studyArea)
        region = {'n': extent['north'], 's': extent['south'], 'w': extent['west'], 'e': extent['east'], 'align': host}
        region = '{n},{s},{w},{e},{align}'.format(**region)
        model_params = self.configuration['POPS']['model'].copy()
        model_name = model_params.pop('model_name')
        flags = model_params.pop('flags')
        model_params.update({'output_series': postfix,
                             'probability_series': probability,
                             'moisture_coefficient_file': os.path.join(os.path.dirname(CONFIG), self.configuration['POPS']['model']['moisture_coefficient_file']),
                             'temperature_coefficient_file': os.path.join(os.path.dirname(CONFIG), self.configuration['POPS']['model']['temperature_coefficient_file'])})

        # run simulation
        self.steeringClient.simulation_set_params(model_name, model_params, flags, region)
        self.steeringClient.simulation_start(False)

    def OnPlay(self, event):
        self.steeringClient.simulation_play()

    def OnPause(self, event):
        self.steeringClient.simulation_pause()

    def OnStepForward(self, event):
        self.steeringClient.simulation_stepf()

    def OnStepBack(self, event):
        self.steeringClient.simulation_stepb()
        
    def OnStop(self, event):
        if self.steeringClient.simulation_is_running():
            self.steeringClient.simulation_stop()
            
    def OnSync(self, event):
        self.steeringClient.simulation_sync_runs()
        
    def OnLoad(self, event):
        # TODO
        self.steeringClient.simulation_load_data()

    def OnClose(self, event):
        self.steeringClient.disconnect()
        self.steeringClient.stop_server()
        # allow clean up in main dialog
        event.Skip()


if __name__ == '__main__':
    app = wx.App()
    top = SteeringFrame(parent=None, title="Steering Client")
    top.Show()
    app.MainLoop()
