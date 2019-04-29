#!/usr/bin/env python2
# -*- coding: utf-8 -*-
"""
Created on Wed Mar 13 11:18:47 2019

@author: anna
"""
import wx
from wx.lib.fancytext import StaticFancyText, RenderToBitmap


def generateHTML(years, lastTreatment, currentView):
    delimiter = '&#9148;'
    html = ''
    style = {'lastTreatment': 'weight="bold" color="black"',
             'currentView':  'weight="bold" color="black" size="20"',
             'default': 'weight="bold" color="gray"'}
    for year in years:
        if year == currentView:
            styl = style['currentView']
        elif year == lastTreatment:
            styl = style['lastTreatment']
        else:
            styl = style['default']
        html += ' <font {style}>{year}</font> '.format(year=year, style=styl)
        if year != years[-1]:
            html += delimiter
    return html
        

class TimeDisplay(wx.Panel):
    def __init__(self, parent, start, end):
        wx.Panel.__init__(self, parent=parent)
        self.years = range(start, end + 1)
        text = generateHTML(self.years, self.years[0], self.years[0])
        self.textCtrl = StaticFancyText(parent, -1, text)
        self.sizer = wx.BoxSizer(wx.VERTICAL)
        self.sizer.Add(self.textCtrl, 1, wx.ALL | wx.ALIGN_CENTER | wx.EXPAND, 5)
        self.SetSizer(self.sizer)
        self.sizer.Fit(self)

    def Update(self, lastTreatment, currentView):
        text = self.GenerateHTML(lastTreatment, currentView)
        bmp = RenderToBitmap(text)
        self.textCtrl.SetBitmap(bmp)
        
    def GenerateHTML(self, lastTreatment, currentView):
        delimiter = '&#9148;'
        html = ''
        style = {'lastTreatment': 'weight="bold" color="black"',
                 'currentView':  'weight="bold" color="black" size="20"',
                 'default': 'weight="bold" color="gray"'}
        for year in self.years:
            if year == currentView:
                styl = style['currentView']
            elif year == lastTreatment:
                styl = style['lastTreatment']
            else:
                styl = style['default']
            html += ' <font {style}>{year}</font> '.format(year=year, style=styl)
            if year != self.years[-1]:
                html += delimiter
        return html
        

class TimeDisplayFrame(wx.Frame):
    def __init__(self, parent, start, end):
        wx.Frame.__init__(self, parent)
        self.timedisplay = TimeDisplay(self, start, end)
        self.slider1 = wx.Slider(self, minValue=start, maxValue=end, value=start)
        self.slider2 = wx.Slider(self, minValue=start, maxValue=end, value=start)
        self.sizer = wx.BoxSizer(wx.VERTICAL)
        self.sizer.Add(self.timedisplay, 1, wx.ALL|wx.ALIGN_CENTER|wx.GROW, border=10)
        self.sizer.Add(self.slider1, 1, wx.ALL|wx.ALIGN_CENTER|wx.GROW, border=15)
        self.sizer.Add(self.slider2, 1, wx.ALL|wx.ALIGN_CENTER|wx.GROW, border=15)
        self.SetSizer(self.sizer)
        self.sizer.Fit(self)
        self.Layout()
        self.SetSize(self.GetBestSize())
        self.slider1.Bind(wx.EVT_SLIDER, self.OnChangeCurrent)
        self.slider2.Bind(wx.EVT_SLIDER, self.OnChangeCurrent)
        
    def OnChangeCurrent(self, evt):
        val1 = self.slider1.GetValue()
        val2 = self.slider2.GetValue()
        self.timedisplay.Update(val1, val2)
        
        
        


if __name__ == "__main__":
    app = wx.App()
    disp = TimeDisplayFrame(None, 2016, 2021)
    disp.Show()
    app.MainLoop()