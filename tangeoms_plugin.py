# -*- coding: utf-8 -*-
"""
Created on Wed Nov 20 14:44:32 2013

@author: anna
"""
import threading
import wx
import time

import wx.lib.newevent

updateGUIEvt, EVT_UPDATE_GUI = wx.lib.newevent.NewCommandEvent()


class TangeomsUpdatePlugin(wx.Dialog):
    def __init__(self, giface, parent):
        wx.Dialog.__init__(self, parent)
        self.giface=giface
        self.parent=parent
        mainSizer = wx.BoxSizer(wx.VERTICAL)
        mainSizer.Add(wx.StaticText(self, label="Press start to start"),
                      proportion=0, flag=wx.EXPAND | wx.ALL, border=5)
        btnStart = wx.Button(self, label="Start")
        btnStop = wx.Button(self, label="Stop")
        btnClose = wx.Button(self, label="Close")

        btnStart.Bind(wx.EVT_BUTTON, lambda evt: self.Start())
        btnStop.Bind(wx.EVT_BUTTON, lambda evt: self.Stop())
        btnClose.Bind(wx.EVT_BUTTON, self.OnClose)
        self.Bind(wx.EVT_CLOSE, self.OnClose)
        self.Bind(EVT_UPDATE_GUI, self.OnUpdate)

        btnSizer = wx.BoxSizer(wx.HORIZONTAL)
        btnSizer.Add(btnStart, proportion=0, flag=wx.ALL, border=2)
        btnSizer.Add(btnStop, proportion=0, flag=wx.ALL, border=2)
        btnSizer.Add(btnClose, proportion=0, flag=wx.ALL, border=2)
        mainSizer.Add(btnSizer, proportion=0, flag=wx.EXPAND | wx.ALL, border=5)

        self.SetSizer(mainSizer)
        mainSizer.Fit(self)

        self.stopEvt = threading.Event()
        self.threadI = threading.Thread(target=updateGUI, args=[self, self.stopEvt])

    def OnClose(self, event):
        self.Stop()
        self.Destroy()

    def Start(self):
        if not self.threadI.isAlive():
            self.threadI.start()

    def Stop(self):
        if self.threadI.isAlive():
            self.stopEvt.set()

    def OnUpdate(self, event):
        self.giface.WriteWarning("bezim")


def updateGUI(target, stopEvent):
    while not stopEvent.is_set():
        time.sleep(1)
        evt = updateGUIEvt(target.GetId())
        wx.PostEvent(target, evt)


def run(giface, guiparent):
    dlg = TangeomsUpdatePlugin(giface, guiparent)
    dlg.Show()


if __name__ == '__main__':
    run(None, None)