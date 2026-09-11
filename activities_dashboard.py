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


PROGRESSBAR_STYLE = """
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
                float: left;
                margin: 0px 0px 0 0;
                background: #F70;
                border-radius: 15px;
                box-shadow: 0px 0px 6px #666 inset;
            }}
            """


class MultipleDashboardFrame(wx.Frame):
    def __init__(
        self, parent, fontsize, maximum, title, formatting_string, vertical=False
    ):
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
                    self.titles.append(
                        wx.StaticText(
                            self, label=self.list_title[i] + ":", style=wx.ALIGN_LEFT
                        )
                    )
                self.labels.append(wx.StaticText(self, style=wx.ALIGN_RIGHT))
                self.gauges.append(wx.Gauge(self, range=self.list_maximum[i]))
            else:
                if title:
                    self.titles.append(
                        wx.StaticText(
                            self, label=self.list_title[i], style=wx.ALIGN_CENTER
                        )
                    )
                self.labels.append(
                    wx.StaticText(self, style=wx.ALIGN_CENTRE_HORIZONTAL)
                )
                self.gauges.append(
                    wx.Gauge(self, range=self.list_maximum[i], style=wx.GA_VERTICAL)
                )
            font = wx.Font(fontsize, wx.DEFAULT, wx.NORMAL, wx.BOLD)
            self.labels[i].SetFont(font)
            if title:
                self.titles[i].SetFont(font)
            if vertical:
                if title:
                    self.sizer.Add(
                        self.titles[i], pos=(i, 0), flag=wx.ALL | wx.ALIGN_BOTTOM
                    )
                self.sizer.Add(self.gauges[i], pos=(i, 1), flag=wx.ALL | wx.EXPAND)
                self.sizer.Add(
                    self.labels[i], pos=(i, 2), flag=wx.ALL | wx.ALIGN_BOTTOM
                )
            else:
                if title:
                    self.sizer.Add(
                        self.titles[i], pos=(0, i), flag=wx.ALL | wx.ALIGN_CENTER
                    )
                extra = wx.BoxSizer(wx.HORIZONTAL)
                extra.AddStretchSpacer()
                extra.Add(self.gauges[i], flag=wx.EXPAND)
                extra.AddStretchSpacer()
                self.sizer.Add(extra, pos=(1, i), flag=wx.ALL | wx.EXPAND)
                self.sizer.Add(
                    self.labels[i], pos=(2, i), flag=wx.ALL | wx.ALIGN_CENTER
                )
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
            print("wrong number of values!")
            return
        for i in range(len(self.gauges)):
            if values[i] is None:
                self.labels[i].SetLabel("")
                self.gauges[i].SetValue(0)
                continue

            self.labels[i].SetLabel(self.list_formatting_string[i].format(values[i]))
            if values[i] > self.list_maximum[i]:
                values[i] = self.list_maximum[i]
            self.gauges[i].SetValue(values[i])
        self.sizer.Layout()
        self.Layout()


class MultipleHTMLDashboardFrame(wx.Frame):
    def __init__(
        self,
        parent,
        fontsize,
        average,
        maximum,
        title,
        formatting_string,
        vertical=False,
        grid=False,
    ):
        wx.Frame.__init__(self, parent, style=wx.NO_BORDER)
        self.panel = wx.Panel(parent=self)
        self.fontsize = fontsize
        self.average = average
        self.vertical = vertical
        self.grid = grid  # grid layout may not be implemented in webkit
        # TODO: average not used yet here
        # TODO: vertical not supported

        # maximum, title and formatting_string are lists
        self.list_maximum = maximum
        self.list_title = title
        self.list_formatting_string = formatting_string
        self.info = ""
        self.values = []
        self.sizer = wx.BoxSizer(wx.VERTICAL)
        if webview:
            self.textCtrl = webview.WebView.New(self)
            values = [None] * len(title)
            html = (
                self._content_grid(values) if self.grid else self._content_table(values)
            )
            self.textCtrl.SetPage(html, "")
            self.sizer.Add(self.textCtrl, 1, wx.ALL | wx.EXPAND, 5)

        self.SetSizer(self.sizer)
        self.sizer.Fit(self.panel)

    def _progressbar(self):
        return PROGRESSBAR_STYLE

    def _head_grid(self):
        return (
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
            """
            + self._progressbar()
            + """
            </style></head><body>
            <div class="grid-container">
            """
        )

    def _head_table(self):
        return (
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
            """
            + self._progressbar()
            + """
            </style></head><body>
            <table style="width:100%; font-size: {fontsize}px;">
            """
        )

    def _end_grid(self):
        return "</div><p>{self.info}</p></body></html>"

    def _end_table(self):
        return f"</table><p>{self.info}</p></body></html>"

    def _progress_element(self, max_value, value):
        # minimum is needed to generate a valid progress element
        value = min(max_value, value)
        return '<progress max="{max}" value="{val}"></progress>'.format(
            max=max_value, val=value
        )

    def _content_grid(self, values):
        div = '<div class="grid-item">{item}</div>'
        html = self._head_grid().format(fontsize=self.fontsize)
        for i in range(len(self.list_title)):
            if values[i] is None:
                values[i] = 0
                label = ""
            else:
                label = self.list_formatting_string[i].format(values[i])
            html += div.format(item=self.list_title[i] + ":")
            html += div.format(
                item=self._progress_element(
                    max_value=self.list_maximum[i], value=values[i]
                )
            )
            html += div.format(item=label)
        html += self._end_grid()
        return html

    def _content_table(self, values):
        div = "<td>{item}</td>"
        html = self._head_table().format(fontsize=self.fontsize)
        for i in range(len(self.list_title)):
            html += "<tr>"
            if values[i] is None:
                values[i] = 0
                label = ""
            else:
                label = self.list_formatting_string[i].format(values[i])
            html += div.format(item=self.list_title[i] + ":")
            html += div.format(
                item=self._progress_element(
                    max_value=self.list_maximum[i], value=values[i]
                )
            )
            html += div.format(item=label)
            html += "</tr>"
        html += self._end_table()
        return html

    def show_value(self, values):
        if len(self.list_title) != len(values):
            print("wrong number of values!")
            return
        self.values = values
        html = self._content_grid(values) if self.grid else self._content_table(values)
        if webview:
            self.textCtrl.SetPage(html, "")

    def set_info(self, msg):
        self.info = msg
        self.show_value(self.values)


DIRECTION_LETTERS = {
    0: "N",
    45: "NE",
    90: "E",
    135: "SE",
    180: "S",
    225: "SW",
    270: "W",
    315: "NW",
}


def direction_to_letter(azimuth):
    """Convert azimuth written by r.pops.spread into a compass letter.

    Returns None for the non-directional value and for anything unparsable.
    """
    try:
        return DIRECTION_LETTERS[int(azimuth)]
    except (TypeError, ValueError, KeyError):
        return None


class QuarantineDashboardFrame(wx.Frame):
    """Shows how close the infestation is to the quarantine boundary.

    The progress bar is inverted on purpose: it fills up as the distance
    shrinks, so a full bar means the infestation reached the boundary.
    """

    def __init__(
        self,
        parent,
        fontsize,
        max_distance,
        title="Distance to quarantine",
        formatting_string="{:.1f} km",
        escape_formatting_string="Escape by end of simulation: {:.0f}%",
        scale=1,
        show_direction=True,
    ):
        wx.Frame.__init__(self, parent, style=wx.NO_BORDER)
        self.panel = wx.Panel(parent=self)
        self.fontsize = fontsize
        self.max_distance = float(max_distance)
        self.title = title
        self.formatting_string = formatting_string
        self.escape_formatting_string = escape_formatting_string
        self.scale = float(scale) if scale else 1
        self.show_direction = show_direction
        self.values = (None, None, False, None)

        self.sizer = wx.BoxSizer(wx.VERTICAL)
        if webview:
            self.textCtrl = webview.WebView.New(self)
            self.textCtrl.SetPage(self._content(*self.values), "")
            self.sizer.Add(self.textCtrl, 1, wx.ALL | wx.EXPAND, 5)

        self.SetSizer(self.sizer)
        self.sizer.Fit(self.panel)

    def _head(self):
        return (
            """<!DOCTYPE html><html><head><style>
            td {{
                white-space: nowrap;
                font-family: sans-serif;
            }}
            table td:nth-child(2) {{
                width: 100%;
            }}
            .danger {{
                color: #C00;
                font-weight: bold;
            }}
            .preview {{
                color: #555;
                font-style: italic;
            }}
            """
            + PROGRESSBAR_STYLE
            + """
            progress.danger::-webkit-progress-value {{
                background: #C00;
            }}
            </style></head><body>
            <table style="width:100%; font-size: {fontsize}px;">
            """
        )

    def _progress_element(self, value, escaped):
        return '<progress class="{cls}" max="{max}" value="{val}"></progress>'.format(
            cls="danger" if escaped else "", max=self.max_distance, val=value
        )

    def _content(self, distance, direction, escaped, escape_probability):
        if escaped:
            # full bar, the boundary has been crossed
            value = self.max_distance
            label = '<span class="danger">ESCAPED</span>'
        elif distance is None:
            value = 0
            label = ""
        else:
            value = min(self.max_distance, max(0, self.max_distance - distance))
            label = self.formatting_string.format(distance / self.scale)
            letter = direction_to_letter(direction)
            if self.show_direction and letter:
                label += " " + letter

        html = self._head().format(fontsize=self.fontsize)
        html += "<tr>"
        html += "<td>{item}</td>".format(item=self.title + ":")
        html += "<td>{item}</td>".format(item=self._progress_element(value, escaped))
        html += "<td>{item}</td>".format(item=label)
        html += "</tr>"
        html += "</table>"
        if escape_probability is not None:
            preview = '<p class="preview" style="font-size: {fontsize}px;">{text}</p>'
            html += preview.format(
                fontsize=int(self.fontsize * 0.8),
                text=self.escape_formatting_string.format(escape_probability * 100),
            )
        html += "</body></html>"
        return html

    def show_value(
        self, distance, direction=None, escaped=False, escape_probability=None
    ):
        """Update the display.

        Distance is in map units, direction is the azimuth as written by the
        model. When the run escaped, distance and direction are not available.
        """
        self.values = (distance, direction, escaped, escape_probability)
        if webview:
            self.textCtrl.SetPage(self._content(*self.values), "")

    def clear(self):
        self.show_value(None)


if __name__ == "__main__":
    app = wx.App()
    test = "html"
    if test == "html":
        fr = MultipleHTMLDashboardFrame(
            parent=None,
            fontsize=10,
            average=1,
            maximum=[200, 100, 20],
            title=["T 1", "T 2", "T 3"],
            formatting_string=["{}", "{}", "{}"],
            vertical=True,
            grid=False,
        )
        fr.SetPosition((700, 200))
        fr.SetSize((850, 800))
        fr.show_value([5000, 20, 1000000])
    elif test == "quarantine":
        fr = QuarantineDashboardFrame(
            parent=None,
            fontsize=20,
            max_distance=10000,
            title="Distance to quarantine",
            formatting_string="{:.1f} km",
            scale=1000,
            show_direction=True,
        )
        fr.SetPosition((700, 200))
        fr.SetSize((500, 150))
        fr.show_value(3400, 90, escaped=False, escape_probability=0.4)
    elif test == "wx":
        fr = MultipleDashboardFrame(
            parent=None,
            fontsize=10,
            maximum=[200, 100, 20],
            title=["T 1", "T 2", "T 3"],
            formatting_string=["{}", "{}", "{}"],
            vertical=True,
        )
        fr.SetPosition((700, 200))
        fr.SetSize((200, 150))
        fr.show_value([200, 20, 0])
    fr.Show()

    app.MainLoop()
