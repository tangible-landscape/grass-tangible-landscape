# -*- coding: utf-8 -*-
"""
Created on Fri Dec 18 16:00:49 2015

@author: gis
"""
import wx

from grass.exceptions import CalledModuleError

class TermitesPanel(wx.Panel):
    def __init__(self, parent, giface):
        wx.Panel.__init__(self, parent)
        self.giface = giface
        mainSizer = wx.BoxSizer(wx.VERTICAL)
        output_name = wx.TextCtrl(self, value="scen1")
        analysis = wx.Button(self, label = "Run")
        analysis.Bind(wx.EVT_BUTTON, lambda evt: self.RunTermites(output_name.GetValue()))
        sizer = wx.BoxSizer(wx.HORIZONTAL)
        sizer.Add(output_name, proportion=1, flag=wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, border=5)
        sizer.Add(analysis, flag=wx.ALIGN_CENTER_VERTICAL)
        mainSizer.Add(sizer, flag=wx.EXPAND | wx.ALL, border=5)
        self.SetSizer(mainSizer)
        mainSizer.Fit(self)
        
    def RunTermites(self, output_name):
        func = 'model_termites'
        habitat = 'habitat_changed'
        init_colonies = 'init_colonies'
        if not output_name:
            return
        import current_analyses
        try:
            reload(current_analyses)
        except:
            pass
        try:
            exec('current_analyses.' + func + '(habitat, init_colonies, output_name)')
        except CalledModuleError, e:
            print e
            return
        for each in self.giface.GetAllMapDisplays():
             each.GetMapWindow().UpdateMap()    