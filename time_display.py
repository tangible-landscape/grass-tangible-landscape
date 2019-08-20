# -*- coding: utf-8 -*-
"""
@brief POPS temporal steering display

This program is free software under the GNU General Public License
(>=v2). Read the file COPYING that comes with GRASS for details.

@author: Anna Petrasova (akratoc@ncsu.edu)
"""
import wx
import wx.html as wxhtml
import wx.html2 as webview


template = """
<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="utf-8">
    <title>Steering</title>
  </head>
  <body bgcolor="#F2F1F0"  style="font-size:{fontsize}px;">
    <div><center>
    {body}
    </center></div>
  </body>
</html>
"""


class SteeringDisplay(wx.Panel):
    def __init__(self, parent, fontsize, start, end, vtype):
        wx.Panel.__init__(self, parent=parent)
        self.years = range(start, end + 1)
        self.fontsize = fontsize
        self.textCtrl = wxhtml.HtmlWindow(self, style=wx.NO_FULL_REPAINT_ON_RESIZE |
                                          wxhtml.HW_SCROLLBAR_NEVER |
                                          wxhtml.HW_NO_SELECTION)
        self.textCtrl = webview.WebView.New(self)
        self.textCtrl.SetPage(template.format(body="", fontsize=self.fontsize), '')
        self.sizer = wx.BoxSizer(wx.VERTICAL)
        self.sizer.Add(self.textCtrl, 1, wx.ALL | wx.ALIGN_CENTER | wx.EXPAND, 5)
        self.SetSizer(self.sizer)
        self.sizer.Fit(self)

    def UpdateText(self, current, currentView, vtype=None):
        text = self.GenerateHTMLSimple(current + self.years[0], currentView + self.years[0], vtype=vtype)
        html = template.format(body=text, fontsize=self.fontsize)
        self.textCtrl.SetPage(html, '')

    def GenerateHTMLSimple(self, current, currentView, vtype):
        delimiter = '&#8594;'
        html = ''
        highlight_style = "border-radius: 0.2em;border:0.1em solid #ccc;background-color:#ccc;"
        style = {'past': 'weight="bold" color="black"'.format(self.fontsize),
                 'current':  'weight="bold" color="black"'.format(int(self.fontsize * 1.5)),
                 'future': 'weight="bold" color="gray"'.format(self.fontsize)}
        for year in self.years:
            highlight = ''
            if year < current:
                styl = style['past']
                delim_styl = style['past']
            elif year == current:
                styl = style['current']
                delim_styl = style['future']
            else:
                styl = style['future']
                delim_styl = style['future']
            if year == currentView:
                highlight = highlight_style
            html += ' <span style=\"{h}\"><font {style}>{year}</font></span> '.format(h=highlight, year=year, style=styl)
            if year != self.years[-1]:
                d = delimiter
                html += '<font {style}> {d} </font>'.format(style=delim_styl, d=d)
        return html

    def GenerateHTMLVType(self, current, currentView, vtype):
        delim_single = '&#9148;'
        delim_prob = '&#9776;'
        delim_split = '&#9887;'
        html = ''
        style = {'past': 'weight="bold" color="black" size="{}"'.format(self.fontsize),
                 'current':  'weight="bold" color="black" size="{}"'.format(int(self.fontsize * 1.5)),
                 'future': 'weight="bold" color="gray" size="{}"'.format(self.fontsize)}
        for year in self.years:
            if year < current:
                styl = style['past']
            elif year == current:
                styl = style['current']
            else:
                styl = style['future']
            html += ' <font {style}>{year}</font> '.format(year=year, style=styl)
            if year != self.years[-1]:
                d = delim_single
                if vtype == 'probability':
                    if year == self.years[0]:
                        d = delim_split
                    else:
                        d = delim_prob
                elif vtype == 'combined':
                    # TODO fix None
                    if year == current:
                        d = delim_split
                    elif year > current:
                        d = delim_prob
                # for now, keep simple until I figure it out
                #d = delim_single
                html += '<font {style}> {d} </font>'.format(style=style['future'], d=d)
        return html


class SteeringDisplayFrame(wx.Frame):
    def __init__(self, parent, fontsize, start, end, vtype, test=False):
        if test:
            wx.Frame.__init__(self, parent)
        else:
            wx.Frame.__init__(self, parent, style=wx.NO_BORDER)
        self.test = test
        self.timedisplay = SteeringDisplay(self, fontsize, start, end, vtype)
        if test:
            self.slider1 = wx.Slider(self, minValue=0, maxValue=(end - start), value=0)
            self.slider2 = wx.Slider(self, minValue=0, maxValue=(end - start), value=0)
        self.sizer = wx.BoxSizer(wx.VERTICAL)
        self.sizer.Add(self.timedisplay, 1, wx.ALL|wx.ALIGN_CENTER|wx.GROW)
        if test:
            self.sizer.Add(self.slider1, 1, wx.ALL|wx.ALIGN_CENTER|wx.GROW, border=15)
            self.sizer.Add(self.slider2, 1, wx.ALL|wx.ALIGN_CENTER|wx.GROW, border=15)
        self.SetSizer(self.sizer)
        self.sizer.Fit(self)
        self.Layout()
        self.SetSize(self.GetBestSize())
        if test:
            self.slider1.Bind(wx.EVT_SLIDER, self.OnChangeCurrent)
            self.slider2.Bind(wx.EVT_SLIDER, self.OnChangeCurrent)

    def UpdateText(self, current, currentView, vtype=None):
        self.timedisplay.UpdateText(current, currentView, vtype=None)

    def OnChangeCurrent(self, evt):
        if self.test:
            val1 = self.slider1.GetValue()
            val2 = self.slider2.GetValue()
            self.timedisplay.UpdateText(val1, val2)


class CurrentViewDisplayFrame(wx.Frame):
    def __init__(self, parent, fontsize, start, end, beginning_of_year, bgcolor=None, fgcolor=None):
        wx.Frame.__init__(self, parent=parent, style=wx.NO_BORDER)
        panel = wx.Panel(self)
        self.years = range(start, end + 1)
        self.beginning_of_year = beginning_of_year
        s = int(fontsize / 2.)
        if self.beginning_of_year:
            year = str(self.years[0])
        else:
            year = str(self.years[0] - 1)
        self.yearCtrl = wx.StaticText(panel, -1, year, style=wx.ALIGN_CENTRE_HORIZONTAL)
        self.yearCtrl.SetFont(wx.Font(fontsize, wx.FONTFAMILY_SWISS, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD))
        self.typeCtrl = wx.StaticText(panel, -1, "forecast", style=wx.ALIGN_CENTRE_HORIZONTAL)
        self.typeCtrl.SetFont(wx.Font(s, wx.FONTFAMILY_SWISS, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD))
        if bgcolor:
            panel.SetBackgroundColour(wx.Colour(*bgcolor))
        if fgcolor:
            self.yearCtrl.SetForegroundColour(wx.Colour(*fgcolor))
            self.typeCtrl.SetForegroundColour(wx.Colour(*fgcolor))
        self.sizer = wx.BoxSizer(wx.VERTICAL)
        self.sizer.Add(self.yearCtrl, 1, wx.ALL | wx.ALIGN_CENTER | wx.EXPAND, 5)
        self.sizer.Add(self.typeCtrl, 0, wx.ALL | wx.ALIGN_CENTER | wx.EXPAND, 5)
        panel.SetSizer(self.sizer)
        self.sizer.Fit(panel)

    def UpdateText(self, year, dtype):
        if self.beginning_of_year:
            year = str(int(year) + self.years[0])
        else:
            year = str(int(year) + self.years[0] - 1)
        self.yearCtrl.SetLabel(year)
        self.typeCtrl.SetLabel(dtype)


class SimpleTimeDisplayFrame(wx.Frame):
    def __init__(self, parent, fontsize):
        wx.Frame.__init__(self, parent, style=wx.NO_BORDER)
        self.label = wx.StaticText(self, style=wx.ALIGN_CENTRE_HORIZONTAL)
        font = wx.Font(fontsize, wx.DEFAULT, wx.NORMAL, wx.BOLD)
        self.label.SetFont(font)
        self.sizer = wx.BoxSizer(wx.VERTICAL)
        self.sizer.Add(self.label, 1, wx.ALL|wx.ALIGN_CENTER|wx.GROW, border=10)
        self.SetSizer(self.sizer)
        self.sizer.Fit(self)

    def UpdateText(self, current):
        self.label.SetLabel(str(current + self.years[0]))

if __name__ == "__main__":
    app = wx.App()
    disp = SteeringDisplayFrame(None, 40, 2016, 2021, None, True)
    disp.SetSize((800, 200))
    disp.Show()
    app.MainLoop()