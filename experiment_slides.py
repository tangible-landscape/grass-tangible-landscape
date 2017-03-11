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
        self.wv.RunScript('Reveal.next()')
