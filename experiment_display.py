# -*- coding: utf-8 -*-
"""
@brief experiment_display

This program is free software under the GNU General Public License
(>=v2). Read the file COPYING that comes with GRASS for details.

@author: Anna Petrasova (akratoc@ncsu.edu)
"""

import numpy as np
from collections import deque

import wx

class DisplayFrame(wx.Frame):
    def __init__(self, parent, fontsize, average, maximum):
        wx.Frame.__init__(self, parent)
        self.maximum = maximum
        self.label = wx.StaticText(self, style=wx.ALIGN_CENTRE_HORIZONTAL)
        self.gauge = wx.Gauge(self, range=maximum, style=wx.GA_VERTICAL)
        self.gauge.SetBackgroundColour(wx.WHITE)
        font = wx.Font(fontsize, wx.DEFAULT, wx.NORMAL, wx.BOLD)
        self.label.SetFont(font)
        self.sizer = wx.BoxSizer(wx.VERTICAL)
        self.sizer.Add(self.gauge, 1, wx.ALL|wx.EXPAND, border=5)
        self.sizer.Add(self.label, 0, wx.ALL|wx.ALIGN_CENTER|wx.GROW, border=10)
        self.SetSizer(self.sizer)
        self.Fit()

        self.values = deque(maxlen=average)

    def show_value(self, value):
        self.values.append(value)
        mean = np.mean(np.array(self.values))
        self.label.SetLabel("{}".format(int(mean)))
        if value > self.maximum:
            value = self.maximum
        self.gauge.SetValue(value)


if __name__ == "__main__":
    app = wx.App()
    fr = DisplayFrame(None, 20, 3, 100)
    fr.SetPosition((500, 100))
    fr.SetSize((100, 500))
    fr.show_value(100)
    fr.Show()
   
    app.MainLoop()
