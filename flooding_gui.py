# -*- coding: utf-8 -*-
"""
Created on Fri Dec 18 16:00:49 2015

@author: gis
"""
import os
import sys
import wx

from grass.exceptions import CalledModuleError
import grass.script as gscript
from utils import get_environment, remove_temp_regions

class FloodingPanel(wx.Panel):
    def __init__(self, parent, giface, runFunction):
        wx.Panel.__init__(self, parent)
        self.giface = giface
        self.runFunction = runFunction
        self.round = 1
        mainSizer = wx.BoxSizer(wx.VERTICAL)
        output_name = wx.TextCtrl(self, value="scen1")
        analysis = wx.Button(self, label = "Run")
        analysis.Bind(wx.EVT_BUTTON, lambda evt: self.RunFlood(output_name.GetValue()))
        reset = wx.Button(self, label = "Reset")
        reset.Bind(wx.EVT_BUTTON, lambda evt: self.Reset())
        breach = wx.Button(self, label = "Breach")
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
        func = 'run_flooding'
        if not output_name:
            return
        import flooding
        try:
            reload(flooding)
        except:
            pass
        self.runFunction(None)
        scan = self.GetGrandParent().data['scan_name']
        real_elev = self.GetGrandParent().data['elevation']
        tmp_regions = []
        env = get_environment(tmp_regions, rast=real_elev)
        try:
            exec('flooding.' + func + '(real_elev="{real}", scanned_elev="{scan}", new="{new}", round={round}, env=env)'.format(real=real_elev,
                 scan=scan, new=output_name, round=self.round))
        except CalledModuleError, e:
            print e
            return
        for each in self.giface.GetAllMapDisplays():
            each.GetMapWindow().UpdateMap()
        remove_temp_regions(tmp_regions)
        self.round += 1