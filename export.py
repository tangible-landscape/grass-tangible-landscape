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

from grass.pydispatch.signal import Signal


class ExportPanel(wx.Panel):
    def __init__(self, parent, giface, settings):
        wx.Panel.__init__(self, parent)
        self.giface = giface
        self.settings = settings
        self.settingsChanged = Signal('ScanningPanel.settingsChanged')

        if 'export' not in self.settings:
            self.settings['export'] = {}
            self.settings['export']['PLY'] = False
            self.settings['export']['PLY_file'] = ''

        if self.settings['export']['PLY_file']:
            initDir = os.path.dirname(self.settings['export']['PLY_file'])
        else:
            initDir = ""
        self.ifPLY = wx.CheckBox(self, label="")
        self.ifPLY.SetValue(self.settings['export']['PLY'])
        self.ifPLY.Bind(wx.EVT_CHECKBOX, self.OnChange)
        self.exportPLY = filebrowse.FileBrowseButton(self, labelText="Export PLY:", fileMode=wx.SAVE,
                                                     startDirectory=initDir, initialValue=self.settings['export']['PLY_file'],
                                                     changeCallback=self.OnChange)

        mainSizer = wx.BoxSizer(wx.VERTICAL)
        sizer = wx.BoxSizer(wx.HORIZONTAL)
        sizer.Add(self.ifPLY, flag=wx.ALL | wx.ALIGN_CENTER_VERTICAL | wx.LEFT, border=3)
        sizer.Add(self.exportPLY, flag=wx.ALL | wx.ALIGN_CENTER_VERTICAL, proportion=1, border=0)
        mainSizer.Add(sizer, flag=wx.EXPAND | wx.ALL, border=5)
        self.SetSizer(mainSizer)
        mainSizer.Fit(self)

    def OnChange(self, event):
        self.settings['export']['PLY'] = self.ifPLY.IsChecked()
        self.settings['export']['PLY_file'] = self.exportPLY.GetValue()
        self.settingsChanged.emit()
