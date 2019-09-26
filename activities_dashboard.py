# -*- coding: utf-8 -*-
"""
@brief activities_dashboard

This program is free software under the GNU General Public License
(>=v2). Read the file COPYING that comes with GRASS for details.

@author: Anna Petrasova (akratoc@ncsu.edu)
"""

import wx


class MultipleDashboardFrame(wx.Frame):
    def __init__(self, parent, fontsize, maximum, title, formatting_string, vertical=False):
        wx.Frame.__init__(self, parent, style=wx.NO_BORDER)

        if isinstance(maximum, list):
            self.list_maximum = maximum
            self.list_title = title
            self.list_formatting_string = formatting_string
        else:
            self.list_maximum = [maximum]
            self.list_title = [title]
            self.list_formatting_string = [formatting_string]

        self.labels = []
        self.titles = []
        self.gauges = []
        self.sizer = wx.GridBagSizer(5, 5)
        for i in range(len(self.list_maximum)):
            if vertical:
                if title:
                    self.titles.append(wx.StaticText(self, label=self.list_title[i] + ':', style=wx.ALIGN_LEFT))
                self.labels.append(wx.StaticText(self, style=wx.ALIGN_RIGHT))
                self.gauges.append(wx.Gauge(self, range=self.list_maximum[i]))
            else:
                if title:
                    self.titles.append(wx.StaticText(self, label=self.list_title[i], style=wx.ALIGN_CENTER))
                self.labels.append(wx.StaticText(self, style=wx.ALIGN_CENTRE_HORIZONTAL))
                self.gauges.append(wx.Gauge(self, range=self.list_maximum[i], style=wx.GA_VERTICAL))
            font = wx.Font(fontsize, wx.DEFAULT, wx.NORMAL, wx.BOLD)
            self.labels[i].SetFont(font)
            if title:
                self.titles[i].SetFont(font)
            if vertical:
                if title:
                    self.sizer.Add(self.titles[i], pos=(i, 0), flag=wx.ALL|wx.ALIGN_BOTTOM)
                self.sizer.Add(self.gauges[i], pos=(i, 1), flag=wx.ALL|wx.EXPAND)
                self.sizer.Add(self.labels[i], pos=(i, 2), flag=wx.ALL|wx.ALIGN_BOTTOM)
            else:
                if title:
                    self.sizer.Add(self.titles[i], pos=(0, i), flag=wx.ALL|wx.ALIGN_CENTER)
                extra = wx.BoxSizer(wx.HORIZONTAL)
                extra.AddStretchSpacer()
                extra.Add(self.gauges[i], flag=wx.EXPAND)
                extra.AddStretchSpacer()
                self.sizer.Add(extra, pos=(1, i), flag=wx.ALL|wx.EXPAND)
                self.sizer.Add(self.labels[i], pos=(2, i), flag=wx.ALL|wx.ALIGN_CENTER)
                self.sizer.AddGrowableCol(i, 0)
        if vertical:
            self.sizer.AddGrowableCol(1, 1)
        else:
            self.sizer.AddGrowableRow(1)
        self.SetSizer(self.sizer)
        self.sizer.Fit(self)

    def show_value(self, values):
        if not isinstance(values, list):
            values = [values]
        if len(self.gauges) != len(values):
            print('wrong number of values!')
            return
        for i in range(len(self.gauges)):
            if values[i] is None:
                self.labels[i].SetLabel('')
                self.gauges[i].SetValue(0)
                continue

            self.labels[i].SetLabel(self.list_formatting_string[i].format(values[i]))
            if values[i] > self.list_maximum[i]:
                values[i] = self.list_maximum[i]
            self.gauges[i].SetValue(values[i])
        self.sizer.Layout()
        self.Layout()


if __name__ == "__main__":
    app = wx.App()
    fr = MultipleDashboardFrame(parent=None, fontsize=10, maximum=[200, 100, 20],
                                title=['T 1', 'T 2', 'T 3'], formatting_string=['{}', '{}', '{}'], vertical=True)
    fr.SetPosition((700, 200))
    fr.SetSize((200, 150))
    fr.show_value([200, 20, 0])
    fr.Show()

    app.MainLoop()
