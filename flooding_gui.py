# -*- coding: utf-8 -*-
"""
Created on Fri Dec 18 16:00:49 2015

@author: gis
"""
import wx

import grass.script as gscript
from utils import run_analyses


class FloodingPanel(wx.Panel):
    def __init__(self, parent, giface, settings, runFunction):
        wx.Panel.__init__(self, parent)
        self.giface = giface
        self.settings = settings
        self.runFunction = runFunction
        self.round = 1
        mainSizer = wx.BoxSizer(wx.VERTICAL)
        output_name = wx.TextCtrl(self, value="scen1")
        analysis = wx.Button(self, label="Run")
        analysis.Bind(wx.EVT_BUTTON, lambda evt: self.RunFlood(output_name.GetValue()))
        reset = wx.Button(self, label="Reset")
        reset.Bind(wx.EVT_BUTTON, lambda evt: self.Reset())
        breach = wx.Button(self, label="Breach")
        breach.Bind(wx.EVT_BUTTON, lambda evt: self.Breach())

        sizer = wx.BoxSizer(wx.HORIZONTAL)
        sizer.Add(wx.StaticText(self, label="Output name:"), flag=wx.ALIGN_CENTER_VERTICAL)
        sizer.Add(output_name, proportion=1, flag=wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, border=5)
        sizer.Add(analysis, flag=wx.ALIGN_CENTER_VERTICAL)
        mainSizer.Add(sizer, flag=wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, border=5)
        sizer = wx.BoxSizer(wx.HORIZONTAL)
        sizer.AddStretchSpacer()
        sizer.Add(reset, flag=wx.ALIGN_CENTER_VERTICAL)
        sizer.Add(breach, flag=wx.ALIGN_CENTER_VERTICAL)
        mainSizer.Add(sizer, flag=wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, border=5)

        self.SetSizer(mainSizer)
        mainSizer.Fit(self)

    def Reset(self):
        self.round = 1

    def Breach(self):
        gscript.run_command('v.extract', input="ridge_points", output="breach", layer=2, random=1, flags='t', overwrite=True)

    def RunFlood(self, output_name):
        if not output_name:
            return

        process = self.runFunction(continuous=False)
        process.wait()

        run_analyses(scan_params=self.settings['scan'], analysesFile=self.settings['analyses']['file'],
                     new=output_name, round=self.round)
        for each in self.giface.GetAllMapDisplays():
            each.GetMapWindow().UpdateMap()
        self.round += 1
