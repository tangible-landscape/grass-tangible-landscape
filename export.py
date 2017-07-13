# -*- coding: utf-8 -*-
"""
@brief GUI panel for export functionality

This program is free software under the GNU General Public License
(>=v2). Read the file COPYING that comes with GRASS for details.

@author: Anna Petrasova (akratoc@ncsu.edu)
"""
import os
import wx
import wx.lib.filebrowsebutton as filebrowse

from gui_core.gselect import Select
from grass.pydispatch.signal import Signal


class OutputPanel(wx.Panel):
    def __init__(self, parent, giface, settings):
        wx.Panel.__init__(self, parent)
        self.giface = giface
        self.settings = settings
        self.settingsChanged = Signal('OutputPanel.settingsChanged')

        if 'output' not in self.settings:
            self.settings['output'] = {}
            self.settings['output']['scan'] = 'scan'
            self.settings['output']['PLY'] = False
            self.settings['output']['PLY_file'] = ''
            self.settings['output']['color'] = False
            self.settings['output']['color_name'] = ''

        if self.settings['output']['PLY_file']:
            initDir = os.path.dirname(self.settings['output']['PLY_file'])
        else:
            initDir = ""

        # scan
        self.scan_name = wx.TextCtrl(self)
        self.scan_name.SetValue(self.settings['output']['scan'])
        self.scan_name.Bind(wx.EVT_TEXT, self.OnChange)

        # color
        self.ifColor = wx.CheckBox(self, label=_("Save color rasters (with postfixes _r, _g, _b):"))
        self.ifColor.SetValue(self.settings['output']['color'])
        self.ifColor.Bind(wx.EVT_CHECKBOX, self.OnChange)
        self.exportColor = Select(self, size=(-1, -1), type='raster')
        self.exportColor.SetValue(self.settings['output']['color_name'])
        self.exportColor.Bind(wx.EVT_TEXT, self.OnChange)
        # PLY
        self.ifPLY = wx.CheckBox(self, label="")
        self.ifPLY.SetValue(self.settings['output']['PLY'])
        self.ifPLY.Bind(wx.EVT_CHECKBOX, self.OnChange)
        self.exportPLY = filebrowse.FileBrowseButton(self, labelText="Export PLY:", fileMode=wx.SAVE,
                                                     startDirectory=initDir, initialValue=self.settings['output']['PLY_file'],
                                                     changeCallback=self.OnChange)

        mainSizer = wx.BoxSizer(wx.VERTICAL)
        sizer = wx.BoxSizer(wx.HORIZONTAL)
        sizer.Add(wx.StaticText(self, label="Name of scanned raster:"), flag=wx.ALL | wx.ALIGN_CENTER_VERTICAL, border=5)
        sizer.Add(self.scan_name, proportion=1, flag=wx.EXPAND | wx.ALL, border=5)
        mainSizer.Add(sizer, flag=wx.EXPAND | wx.ALL, border=5)
        sizer = wx.BoxSizer(wx.HORIZONTAL)
        sizer.Add(self.ifColor, flag=wx.ALIGN_CENTER_VERTICAL, border=5)
        sizer.Add(self.exportColor, proportion=1, flag=wx.ALIGN_CENTER_VERTICAL, border=5)
        mainSizer.Add(sizer, flag=wx.EXPAND | wx.ALL, border=5)
        sizer = wx.BoxSizer(wx.HORIZONTAL)
        sizer.Add(self.ifPLY, flag=wx.ALL | wx.ALIGN_CENTER_VERTICAL | wx.LEFT, border=3)
        sizer.Add(self.exportPLY, flag=wx.ALL | wx.ALIGN_CENTER_VERTICAL, proportion=1, border=0)
        mainSizer.Add(sizer, flag=wx.EXPAND | wx.ALL, border=5)
        self.SetSizer(mainSizer)
        mainSizer.Fit(self)

    def OnChange(self, event):
        self.settings['output']['scan'] = self.scan_name.GetValue()
        self.settings['output']['color'] = self.ifColor.IsChecked()
        self.settings['output']['color_name'] = self.exportColor.GetValue()
        self.settings['output']['PLY'] = self.ifPLY.IsChecked()
        self.settings['output']['PLY_file'] = self.exportPLY.GetValue()
        self.settingsChanged.emit()
