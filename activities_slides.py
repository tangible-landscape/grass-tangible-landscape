# -*- coding: utf-8 -*-
"""
@brief activities_slides

For reveal.js presentations embedded in wxPython GUI

This program is free software under the GNU General Public License
(>=v2). Read the file COPYING that comes with GRASS for details.

@author: Anna Petrasova (akratoc@ncsu.edu)
"""
import wx
import wx.html2 as webview


class Slides(wx.Frame):
    def __init__(self, parent):
        wx.Frame.__init__(self, parent=parent)
        sizer = wx.BoxSizer(wx.VERTICAL)
        self.wv = webview.WebView.New(self)
        sizer.Add(self.wv, 1, wx.EXPAND)
        self.SetSizer(sizer)

    def LoadURL(self, url):
        self.wv.LoadURL(url)

    def Next(self):
        self.wv.RunScript("Reveal.next()")
