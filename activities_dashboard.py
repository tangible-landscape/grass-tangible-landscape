# -*- coding: utf-8 -*-
"""
@brief activities_dashboard

This program is free software under the GNU General Public License
(>=v2). Read the file COPYING that comes with GRASS for details.

@author: Anna Petrasova (akratoc@ncsu.edu)
"""

import wx
try:
    import wx.html2 as webview
except ImportError:
    webview = None


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



class MultipleHTMLDashboardFrame(wx.Frame):
    def __init__(self, parent, fontsize, maximum, title,
                 formatting_string, vertical=False, grid=False):
        wx.Frame.__init__(self, parent, style=wx.NO_BORDER)
        self.panel = wx.Panel(parent=self)
        self.fontsize = fontsize
        self.vertical = vertical
        self.grid = grid  # grid layout may not be implemented in webkit
        # TODO: vertical not supported

        # maximum, title and formatting_string are lists
        self.list_maximum = maximum
        self.list_title = title
        self.list_formatting_string = formatting_string

        self.sizer = wx.BoxSizer(wx.VERTICAL)
        if webview:
            self.textCtrl = webview.WebView.New(self)
            values=[None] * len(title)
            html = self._content_grid(values) if self.grid else self._content_table(values)
            self.textCtrl.SetPage(html, '')
            self.sizer.Add(self.textCtrl, 1, wx.ALL | wx.ALIGN_CENTER | wx.EXPAND, 5)

        self.SetSizer(self.sizer)
        self.sizer.Fit(self.panel)

    def _progressbar(self):
        return \
        """
        progress {{
            display: inline-block;
            width: 100%;
            padding: 0px 0 0 0;
            margin: 0;
            background: none;
            border: 0;
            border-radius: 15px;
            text-align: left;
            position: relative;
            font-family: sans-serif;
            font-size: {fontsize}px;
        }}
        progress::-webkit-progress-bar {{
            display: inline-block;
            width: 100%;
            margin: 0 auto;
            background-color: #CCC;
            border-radius: 15px;
            box-shadow: 0px 0px 6px #777 inset;
        }}
        progress::-webkit-progress-value {{
            display: inline-block;
            width: 100%;
            float: left;
            margin: 0px 0px 0 0;
            background: #F70;
            border-radius: 15px;
            box-shadow: 0px 0px 6px #666 inset;
        }}
        """
    def _head_grid(self):
        return \
        """<!DOCTYPE html><html><head><style>
        .grid-container {{
          display: grid;
          grid-template-columns: auto 1fr auto;
          padding: 0px;
        }}
        .grid-item {{
          background-color: rgba(255, 255, 255, 0.8);
          padding: 0px;
          font-size: {fontsize}px;
          text-align: left;
          white-space: nowrap;
        }}
        """ \
        + self._progressbar() + \
        """
        </style></head><body>
        <div class="grid-container">
        """
    def _head_table(self):
        return \
        """<!DOCTYPE html><html><head><style>
        td {{
            white-space: nowrap;
        }}
        /* There are simpler solutions than
           table width, but work only in presumably
           newer browsers. */
        table td:nth-child(2) {{
            width: 100%;
        }}
        """ \
        + self._progressbar() + \
        """
        </style></head><body>
        <table style="width:100%">
        """

    def _end_grid(self):
        return "</div></body></html>"

    def _end_table(self):
        return "</table></body></html>"

    def _progress_element(self, max_value, value):
        # minimum is needed to generate a valid progress element
        value = min(max_value, value)
        return '<progress max="{max}" value="{val}"></progress>'.format(
            max=max_value, val=value)

    def _content_grid(self, values):
        div = '<div class="grid-item">{item}</div>'
        html = self._head_grid().format(fontsize=self.fontsize)
        for i in range(len(self.list_title)):
            if values[i] is None:
                values[i] = 0
                label = ''
            else:
                label = self.list_formatting_string[i].format(values[i])
            html += div.format(item=self.list_title[i] + ':')
            html += div.format(item=self._progress_element(
                max_value=self.list_maximum[i], value=values[i]))
            html += div.format(item=label)
        html += self._end_grid()
        return html

    def _content_table(self, values):
        div = '<td>{item}</td>'
        html = self._head_table().format(fontsize=self.fontsize)
        for i in range(len(self.list_title)):
            html += '<tr>'
            if values[i] is None:
                values[i] = 0
                label = ''
            else:
                label = self.list_formatting_string[i].format(values[i])
            html += div.format(item=self.list_title[i] + ':')
            html += div.format(item=self._progress_element(
                max_value=self.list_maximum[i], value=values[i]))
            html += div.format(item=label)
            html += '</tr>'
        html += self._end_table()
        return html

    def show_value(self, values):
        if len(self.list_title) != len(values):
            print('wrong number of values!')
            return
        html = self._content_grid(values) if self.grid else self._content_table(values)
        if webview:
            self.textCtrl.SetPage(html, '')


if __name__ == "__main__":
    app = wx.App()
    test = 'html'
    if test == 'html':
        fr = MultipleHTMLDashboardFrame(
            parent=None,
            fontsize=10,
            average=1,
            maximum=[200, 100, 20],
            title=['T 1', 'T 2', 'T 3'],
            formatting_string=['{}', '{}', '{}'],
            vertical=True,
            grid=False)
        fr.SetPosition((700, 200))
        fr.SetSize((850, 800))
        fr.show_value([5000, 20, 1000000])
    elif test == 'wx':
        fr = MultipleDashboardFrame(parent=None, fontsize=10, maximum=[200, 100, 20],
                                    title=['T 1', 'T 2', 'T 3'], formatting_string=['{}', '{}', '{}'], vertical=True)
        fr.SetPosition((700, 200))
        fr.SetSize((200, 150))
        fr.show_value([200, 20, 0])
    fr.Show()

    app.MainLoop()
