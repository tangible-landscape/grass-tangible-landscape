"""
@brief Core wrapped wxpython widgets

Taken from GRASS GIS gui/wxpython/gui_core/wrap.py

This program is free software under the GNU General Public License
(>=v2). Read the file COPYING that comes with GRASS for details.

@author: Anna Petrasova (akratoc@ncsu.edu)
"""

import wx
wxPythonPhoenix = False
if 'phoenix' in wx.version():
    wxPythonPhoenix = True

gtk3 = True if 'gtk3' in wx.PlatformInfo else False


class Button(wx.Button):
    """Wrapper around wx.Button to have more control
    over the widget on different platforms/wxpython versions"""
    def __init__(self, *args, **kwargs):
        wx.Button.__init__(self, *args, **kwargs)

    def SetToolTip(self, tip):
        if wxPythonPhoenix:
            wx.Button.SetToolTip(self, tipString=tip)
        else:
            wx.Button.SetToolTipString(self, tip)


class TextCtrl(wx.TextCtrl):
    """Wrapper around wx.TextCtrl to have more control
    over the widget on different platforms/wxpython versions"""
    def __init__(self, *args, **kwargs):
        wx.TextCtrl.__init__(self, *args, **kwargs)

    def SetToolTip(self, tip):
        if wxPythonPhoenix:
            wx.TextCtrl.SetToolTip(self, tipString=tip)
        else:
            wx.TextCtrl.SetToolTipString(self, tip)


class BitmapButton(wx.BitmapButton):
    """Wrapper around wx.BitmapButton to have more control
    over the widget on different platforms/wxpython versions"""
    def __init__(self, *args, **kwargs):
        wx.BitmapButton.__init__(self, *args, **kwargs)

    def SetToolTip(self, tip):
        if wxPythonPhoenix:
            wx.BitmapButton.SetToolTip(self, tipString=tip)
        else:
            wx.BitmapButton.SetToolTipString(self, tip)


class CheckBox(wx.CheckBox):
    """Wrapper around wx.CheckBox to have more control
    over the widget on different platforms/wxpython versions"""
    def __init__(self, *args, **kwargs):
        wx.CheckBox.__init__(self, *args, **kwargs)

    def SetToolTip(self, tip):
        if wxPythonPhoenix:
            wx.CheckBox.SetToolTip(self, tipString=tip)
        else:
            wx.CheckBox.SetToolTipString(self, tip)


class SpinCtrl(wx.SpinCtrl):
    """Wrapper around wx.SpinCtrl to have more control
    over the widget on different platforms"""

    gtk3MinSize = 130

    def __init__(self, *args, **kwargs):
        if gtk3:
            if 'size' in kwargs:
                kwargs['size'] = wx.Size(max(self.gtk3MinSize, kwargs['size'][0]), kwargs['size'][1])
            else:
                kwargs['size'] = wx.Size(self.gtk3MinSize, -1)

        wx.SpinCtrl.__init__(self, *args, **kwargs)

    def SetToolTip(self, tip):
        if wxPythonPhoenix:
            wx.SpinCtrl.SetToolTip(self, tipString=tip)
        else:
            wx.SpinCtrl.SetToolTipString(self, tip)


def BitmapFromImage(image, depth=-1):
    if wxPythonPhoenix:
        return wx.Bitmap(img=image, depth=depth)
    else:
        return wx.BitmapFromImage(image, depth=depth)


def ImageFromStream(stream, type=wx.BITMAP_TYPE_ANY, index=-1):
    if wxPythonPhoenix:
        return wx.Image(stream=stream, type=type, index=index)
    else:
        return wx.ImageFromStream(stream=stream, type=type, index=index)
