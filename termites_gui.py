# -*- coding: utf-8 -*-
"""
Created on Fri Dec 18 16:00:49 2015

@author: gis
"""
import os
import sys
import wx
import random

sys.path.append(os.path.join(os.environ['GISBASE'], "etc", "gui", "wxpython"))
from gui_core.gselect import Select
import grass.script as gscript
from grass.exceptions import CalledModuleError

class TermitesPanel(wx.Panel):
    def __init__(self, parent, giface):
        wx.Panel.__init__(self, parent)
        self.giface = giface
        
        self.colonies = 'init_colonies'
        self.habitat_orig = 'habitat_block_clip'
        self.habitat = 'habitat_changed'
        self.round = 1
        mainSizer = wx.BoxSizer(wx.VERTICAL)
        output_name = wx.TextCtrl(self, value="scen1")
        analysis_baseline = wx.Button(self, label = "Run baseline")
        analysis = wx.Button(self, label = "Run")
        perturb = wx.Button(self, label = "Randomize")
        self.colonies_select = Select(self, size=(-1, -1), type='vector')
        self.colonies_select.SetValue('init_colonies@PERMANENT')
        analysis_baseline.Bind(wx.EVT_BUTTON, lambda evt: self.RunTermites(output_name.GetValue(), self.colonies_select.GetValue(), self.habitat_orig, True))
        analysis.Bind(wx.EVT_BUTTON, lambda evt: self.RunTermites(output_name.GetValue(), self.colonies_select.GetValue(), self.habitat, False))
        perturb.Bind(wx.EVT_BUTTON, lambda evt: self.Randomize())
        
        sizer = wx.BoxSizer(wx.HORIZONTAL)
        sizer.Add(wx.StaticText(self, label="Colonies:"), flag=wx.ALIGN_CENTER_VERTICAL)
        sizer.Add(self.colonies_select, proportion=1, flag=wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, border=5)
        sizer.Add(perturb, flag=wx.EXPAND|wx.ALL, border = 5)
        mainSizer.Add(sizer, flag=wx.EXPAND | wx.ALL, border=5)
        
        sizer = wx.BoxSizer(wx.HORIZONTAL)
        sizer.Add(wx.StaticText(self, label="Output name:"), flag=wx.ALIGN_CENTER_VERTICAL)
        sizer.Add(output_name, proportion=1, flag=wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, border=5)
        sizer.Add(analysis_baseline, flag=wx.ALIGN_CENTER_VERTICAL)
        sizer.Add(analysis, flag=wx.ALIGN_CENTER_VERTICAL)
        mainSizer.Add(sizer, flag=wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, border=5)

        self.SetSizer(mainSizer)
        mainSizer.Fit(self)
        
    def RunTermites(self, output_name, colonies, habitat, baseline):
        func = 'model_termites'
        if not output_name:
            return
        import current_analyses
        try:
            reload(current_analyses)
        except:
            pass
        if baseline:
            self.round = 1
        try:
            exec('current_analyses.' + func + '(habitat, colonies, output_name, self.round)')
        except CalledModuleError, e:
            print e
            return
        for each in self.giface.GetAllMapDisplays():
             each.GetMapWindow().UpdateMap()
        self.round += 1

    def Randomize(self):
        out = 'init_colonies'
        gscript.run_command('v.perturb', input='init_colonies@PERMANENT',
                            output=out, distribution='normal',
                            parameters='0,100', seed=random.randint(1, 1e6), overwrite=True, quiet=True)
        self.colonies_select.SetValue(out)
