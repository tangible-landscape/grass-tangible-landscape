# -*- coding: utf-8 -*-
"""
@brief SOD GUI

This program is free software under the GNU General Public License
(>=v2). Read the file COPYING that comes with GRASS for details.

@author: Anna Petrasova (akratoc@ncsu.edu)
"""
import os
import socket
import threading
import Queue
import requests
import wx

import grass.script as gscript
from grass.pydispatch.signal import Signal

from tangible_utils import addLayers

TMP_DIR = '/tmp/'


class SODPanel(wx.Panel):
    def __init__(self, parent, giface, settings, scaniface):
        wx.Panel.__init__(self, parent)
        self.env = None
        self.giface = giface
        self.parent = parent
        self.settings = settings
        self.scaniface = scaniface
        self.settingsChanged = Signal('ColorInteractionPanel.settingsChanged')

        self.socket = None
        self.isRunningClientThread = False
        self.clientthread = None
        self.timer = wx.Timer(self)
        self.speed = 1000  # 1 second per year
        self.resultsToDisplay = Queue.Queue()

        if 'SOD' not in self.settings:
            self.settings['SOD'] = {}

        self.urlDashboard = wx.TextCtrl(self)
        self.urlSteering = wx.TextCtrl(self)
        btnConnect = wx.Button(self, label=u"\u21BB")
        self.players = wx.Choice(self, choices=[])

        initBtn = wx.Button(self, label="Initialize")
        runBtn = wx.Button(self, label="Run")
        stopBtn = wx.Button(self, label="Stop")

        btnConnect.Bind(wx.EVT_BUTTON, lambda evt: self._connect())
        initBtn.Bind(wx.EVT_BUTTON, lambda evt: self._init())
        runBtn.Bind(wx.EVT_BUTTON, lambda evt: self._run())
        stopBtn.Bind(wx.EVT_BUTTON, lambda evt: self._stop())

        self.Bind(wx.EVT_TIMER, self._displayResult, self.timer)

        self.mainSizer = wx.BoxSizer(wx.VERTICAL)
        sizer = wx.BoxSizer(wx.HORIZONTAL)
        sizer.Add(wx.StaticText(self, label="Dashboard URL:"), flag=wx.ALIGN_CENTER_VERTICAL)
        sizer.Add(self.urlDashboard, proportion=1, flag=wx.ALIGN_CENTER_VERTICAL, border=5)
        self.mainSizer.Add(sizer, flag=wx.EXPAND | wx.ALL, border=5)
        sizer = wx.BoxSizer(wx.HORIZONTAL)
        sizer.Add(wx.StaticText(self, label="Steering URL:"), flag=wx.ALIGN_CENTER_VERTICAL)
        sizer.Add(self.urlSteering, proportion=1, flag=wx.ALIGN_CENTER_VERTICAL, border=5)
        self.mainSizer.Add(sizer, flag=wx.EXPAND | wx.ALL, border=5)
        sizer = wx.BoxSizer(wx.HORIZONTAL)
        sizer.Add(btnConnect, proportion=1, flag=wx.ALIGN_CENTER_VERTICAL, border=5)
        self.mainSizer.Add(sizer, flag=wx.EXPAND | wx.ALL, border=5)
        sizer = wx.BoxSizer(wx.HORIZONTAL)
        sizer.Add(wx.StaticText(self, label="Players:"), flag=wx.ALIGN_CENTER_VERTICAL)
        sizer.Add(self.players, proportion=1, flag=wx.ALIGN_CENTER_VERTICAL, border=5)
        self.mainSizer.Add(sizer, flag=wx.EXPAND | wx.ALL, border=5)
        sizer = wx.BoxSizer(wx.HORIZONTAL)
        sizer.Add(initBtn, proportion=1, flag=wx.ALIGN_CENTER_VERTICAL, border=5)
        sizer.Add(runBtn, proportion=1, flag=wx.ALIGN_CENTER_VERTICAL, border=5)
        sizer.Add(stopBtn, proportion=1, flag=wx.ALIGN_CENTER_VERTICAL, border=5)
        self.mainSizer.Add(sizer, flag=wx.EXPAND | wx.ALL, border=5)
        self.SetSizer(self.mainSizer)
        self.mainSizer.Fit(self)

    def _connect(self):
        self._connectDashboard()
        self._connectSteering()

    def _connectSteering(self):
        if self.socket:
            return
        urlS = self.urlSteering.GetValue()
        if not urlS:
            return
        urlS = urlS.split(':')
        self.socket = socket.socket()
#        self.s = ssl.wrap_socket(self.s, cert_reqs=ssl.CERT_REQUIRED,
#                                 certfile="/etc/ssl/certs/SOD.crt",
#                                 keyfile="/etc/ssl/private/ssl-cert-snakeoil.key",
#                                 ca_certs="/etc/ssl/certs/test_certificate.crt")
        try:
            self.socket.connect((urlS[0], int(urlS[1])))
        except socket.error, exc:
            self.giface.WriteError("Error connecting to steering server: {}".format(exc))
            self.socket = None
            return

        self.isRunningClientThread = True
        self.clientthread = threading.Thread(target=self._client, args=(self.resultsToDisplay, ))
        self.clientthread.start()

    def _connectDashboard(self):
        # reload players
        urlD = self.urlDashboard.GetValue()
        if urlD:
            if not urlD.startswith('http'):
                urlD = 'http://' + urlD + '/players'
            try:
                resp = requests.get(url=urlD)
                players = resp.json()
                current = self.players.GetItems()
                for player in players:
                    if player and player not in current:
                        self.players.Append(player['name'])
                if players:
                    self.players.SetSelection(0)
            except requests.ConnectionError:
                return

    def _client(self, resultsToDisplay):
        while self.isRunningClientThread:
            data = self.socket.recv(1024)
            if not data:
                # GUI received close from server
                # finish while loop
                self.socket.close()
                continue
            message = data.split(':')
            if message[0] == 'clientfile':
                _, fsize, path = message
                with open(message[2], 'rb') as f:
                    data = f.read()
                    try:
                        self.socket.sendall(data)
                    except socket.error:
                        print 'erroro sending file'
            elif message[0] == 'serverfile':
                # receive file
                fsize, path = int(message[1]), message[2]
                self.socket.sendall(data)
                data = self.socket.recv(1024)
                total_received = len(data)
                new_path = os.path.join(TMP_DIR, os.path.basename(path))
                f = open(new_path, 'wb')
                f.write(data)
                while(total_received < fsize):
                    data = self.socket.recv(1024)
                    total_received += len(data)
                    f.write(data)
                f.close()
                gscript.run_command('r.unpack', input=new_path, overwrite=True, quiet=True)
                name = os.path.basename(path).strip('.pack')
                resultsToDisplay.put(name)

    def _init(self):
        message = 'cmd:start'
        player = self.players.GetStringSelection()
        message += ':output_series={}'.format(player)
        self.timer.Start(self.speed)
        self.socket.sendall(message)

    def _run(self):
        self.socket.sendall('cmd:play')

    def _stop(self):
        self.socket.sendall('cmd:end')
        self.timer.Stop()

    def _displayResult(self, event):
        if not self.resultsToDisplay.empty():
            name = self.resultsToDisplay.get()
            cmd = ['d.rast', 'map={}'.format(name)]
            evt = addLayers(layerSpecs=[dict(ltype='raster', name=name, cmd=cmd, checked=True), ])
            self.scaniface.postEvent(evt)

    def OnClose(self, event):
        # first set variable to skip out of thread once possible
        self.isRunningClientThread = False
        try:
            # send message to server that we finish sending
            # then we receive empty response, see above
            if self.socket:
                self.socket.shutdown(socket.SHUT_WR)
        except socket.error, e:
            print e
            pass
        # wait for ending the thread
        if self.clientthread and self.clientthread.isAlive():
            self.clientthread.join()
        # allow clean up in main dialog
        event.Skip()
