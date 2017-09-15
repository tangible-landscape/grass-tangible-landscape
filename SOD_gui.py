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
import json
import wx
import wx.lib.newevent
import wx.lib.filebrowsebutton as filebrowse

from gui_core.gselect import Select
import grass.script as gscript
from grass.pydispatch.signal import Signal

from tangible_utils import addLayers, get_environment

from SOD_dashboard import DashBoardRequests, RadarData, BarData


ProcessForDashboardEvent, EVT_PROCESS_NEW_EVENT = wx.lib.newevent.NewEvent()
ProcessBaseline, EVT_PROCESS_BASELINE_NEW_EVENT = wx.lib.newevent.NewEvent()
TMP_DIR = '/tmp/test_SOD/'


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
        self.playerByIds = self.playersByName = None
        self.eventsByIds = self.eventsByName = None
        self.configFile = ''
        self.configuration = {}
        self.current = 0
        self.baselineEnv = None

        self.dashboard = DashBoardRequests()
        self.radarBaseline = None
        self.barBaseline = None
        self.bar = None
        self.radar = {}
        
        self.maxTrees = 0  # how many max trees in cells we have for setting right color table

        if 'SOD' not in self.settings:
            self.settings['SOD'] = {}
            self.settings['SOD']['config'] = ''
        else:
            self.configFile = self.settings['SOD']['config']

        self.infoBar = wx.InfoBar(self)
        self.urlDashboard = wx.TextCtrl(self, value="localhost:3000")
        self.urlSteering = wx.TextCtrl(self, value="localhost:8888")
        # config file
        self.configFileCtrl = filebrowse.FileBrowseButton(self, labelText='Configuration:', changeCallback=self._loadConfiguration)
        self.configFileCtrl.SetValue(self.configFile, 0)
        btnConnect = wx.Button(self, label=u"\u21BB")
        # events
        self.eventsCtrl = wx.Choice(self, choices=[])
        self.playersCtrl = wx.Choice(self, choices=[])
        self.attemptCtrl = wx.Choice(self, choices=[])
        self.deleteAttempt = wx.Button(self, label="Delete")
        self.eventsCtrl.Bind(wx.EVT_CHOICE, self._onEventChanged)
        self.playersCtrl.Bind(wx.EVT_CHOICE, self._onPlayerChanged)
        self.deleteAttempt.Bind(wx.EVT_BUTTON, lambda evt: self.DeleteAttempt())
        # study area
        self.studySelect = Select(self, size=(-1, -1), type='raster')
        baselineButton = wx.Button(self, label="Compute baseline")
        # treatment area
        self.treatmentSelect = Select(self, size=(-1, -1), type='raster')
        startTreatmentButton = wx.Button(self, label="Start")
        stopTreatmentButton = wx.Button(self, label="Stop")

        runBtn = wx.Button(self, label="Run")
        stopBtn = wx.Button(self, label="Stop")

        btnConnect.Bind(wx.EVT_BUTTON, lambda evt: self._connect())
        runBtn.Bind(wx.EVT_BUTTON, lambda evt: self.RunSimulation())
        stopBtn.Bind(wx.EVT_BUTTON, lambda evt: self._stop())
        baselineButton.Bind(wx.EVT_BUTTON, lambda evt: self._computeBaseline())
        startTreatmentButton.Bind(wx.EVT_BUTTON, lambda evt: self.StartTreatment())
        stopTreatmentButton.Bind(wx.EVT_BUTTON, lambda evt: self.StopTreatment())

        self.Bind(wx.EVT_TIMER, self._displayResult, self.timer)
        self.Bind(EVT_PROCESS_NEW_EVENT, self._processForDashboard)
        self.Bind(EVT_PROCESS_BASELINE_NEW_EVENT, self._processBaseline)

        self.mainSizer = wx.BoxSizer(wx.VERTICAL)
        self.mainSizer.Add(self.infoBar, flag=wx.EXPAND)
        sizer = wx.BoxSizer(wx.HORIZONTAL)
        sizer.Add(wx.StaticText(self, label="Dashboard URL:"), flag=wx.ALIGN_CENTER_VERTICAL)
        sizer.Add(self.urlDashboard, proportion=1, flag=wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, border=5)
        sizer.Add(wx.StaticText(self, label="Steering URL:"), flag=wx.ALIGN_CENTER_VERTICAL)
        sizer.Add(self.urlSteering, proportion=1, flag=wx.ALIGN_CENTER_VERTICAL, border=5)
        sizer.Add(btnConnect, flag=wx.ALIGN_CENTER_VERTICAL, border=5)
        self.mainSizer.Add(sizer, flag=wx.EXPAND | wx.ALL, border=5)
        sizer = wx.BoxSizer(wx.HORIZONTAL)
        sizer.Add(self.configFileCtrl, proportion=1, flag=wx.ALIGN_CENTER_VERTICAL, border=5)
        self.mainSizer.Add(sizer, flag=wx.EXPAND | wx.ALL, border=5)

        sizer = wx.BoxSizer(wx.HORIZONTAL)
        sizer.Add(wx.StaticText(self, label="Events:"), flag=wx.ALIGN_CENTER_VERTICAL)
        sizer.Add(self.eventsCtrl, proportion=1, flag=wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, border=5)
        sizer.Add(wx.StaticText(self, label="Players:"), flag=wx.ALIGN_CENTER_VERTICAL)
        sizer.Add(self.playersCtrl, proportion=1, flag=wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, border=5)
        sizer.Add(wx.StaticText(self, label="Attempts:"), flag=wx.ALIGN_CENTER_VERTICAL)
        sizer.Add(self.attemptCtrl, proportion=0, flag=wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, border=5)
        sizer.Add(self.deleteAttempt, proportion=0, flag=wx.ALIGN_CENTER_VERTICAL, border=5)
        self.mainSizer.Add(sizer, flag=wx.EXPAND | wx.ALL, border=5)
        sizer = wx.BoxSizer(wx.HORIZONTAL)
        sizer.Add(wx.StaticText(self, label="Study area:"), proportion=1, flag=wx.ALIGN_CENTER_VERTICAL)
        sizer.Add(self.studySelect, proportion=1, flag=wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, border=5)
        sizer.Add(baselineButton, proportion=2, flag=wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, border=5)
        self.mainSizer.Add(sizer, flag=wx.EXPAND | wx.ALL, border=5)
        sizer = wx.BoxSizer(wx.HORIZONTAL)
        sizer.Add(wx.StaticText(self, label="Treatment area:"), proportion=1, flag=wx.ALIGN_CENTER_VERTICAL)
        sizer.Add(self.treatmentSelect, proportion=1, flag=wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, border=5)
        sizer.Add(startTreatmentButton, proportion=1, flag=wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, border=5)
        sizer.Add(stopTreatmentButton, proportion=1, flag=wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, border=5)
        self.mainSizer.Add(sizer, flag=wx.EXPAND | wx.ALL, border=5)
        sizer = wx.BoxSizer(wx.HORIZONTAL)
        sizer.Add(runBtn, proportion=1, flag=wx.ALIGN_CENTER_VERTICAL, border=5)
        sizer.Add(stopBtn, proportion=1, flag=wx.ALIGN_CENTER_VERTICAL, border=5)
        self.mainSizer.Add(sizer, flag=wx.EXPAND | wx.ALL, border=5)
        self.SetSizer(self.mainSizer)
        self.mainSizer.Fit(self)

        if self.configFile:
            try:
                with open(self.configFile, 'r') as f:
                    self.configuration = json.load(f)
                    # this should reset the analysis file only when configuration is successfully loaded
                    self.settings['analyses']['file'] = ''
            except IOError:
                self.configFile = None

        self._bindButtons()

    def _connect(self):
        self._connectDashboard()
        self._connectSteering()
        self._loadBaseline()
        self._loadCharts()

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
                urlD = 'http://' + urlD
            self.dashboard.set_root_URL(urlD)
            self.eventsByIds = dict(zip(*self.dashboard.get_events()))
            self.eventsByName = dict(reversed(item) for item in self.eventsByIds.items())
            self.eventsCtrl.SetItems(self.eventsByIds.values())
            self.eventsCtrl.SetSelection(0)
            self.playersByIds = dict(zip(*self.dashboard.get_players(self.eventsByName[self.eventsCtrl.GetStringSelection()])))
            self.playersByName = dict(reversed(item) for item in self.playersByIds.items())
            self.playersCtrl.SetItems(self.playersByIds.values())
            self.playersCtrl.SetSelection(0)

    def _onEventChanged(self, event):
        selectedEventName = self.eventsCtrl.GetStringSelection()
        self.playersByIds = dict(zip(*self.dashboard.get_players(self.eventsByName[selectedEventName])))
        self.playersByName = dict(reversed(item) for item in self.playersByIds.items())
        self.playersCtrl.SetItems(self.playersByIds.values())
        self.playersCtrl.SetSelection(0)

    def _onPlayerChanged(self, event):
        selectedPlayer = self.playersCtrl.GetStringSelection()
        attempts = []
        if self.bar:
            attempts = self.bar.getAllAttempts(selectedPlayer)
        self.attemptCtrl.SetItems([str(a) for a in attempts])
        if attempts:
            self.attemptCtrl.SetStringSelection(str(max(attempts)))

    def DeleteAttempt(self):
        event = self.eventsCtrl.GetStringSelection()
        selectedPlayer = self.playersCtrl.GetStringSelection()
        attempt = self.attemptCtrl.GetStringSelection()
        if attempt != wx.NOT_FOUND:
            if self.bar:
                self.bar.removeAttempt(selectedPlayer, int(attempt))
                jsonfile = os.path.join(self.configuration['logDir'], 'bar.json')
                self.dashboard.post_data_bar(jsonfile=jsonfile, eventId=self.eventsByName[event])
            if self.radar:
                self.radar[selectedPlayer].removeAttempt(int(attempt))
                jsonfile = os.path.join(self.configuration['logDir'], 'radar_{}.json'.format(selectedPlayer))
                self.dashboard.post_data_radar(jsonfile, self.eventsByName[event], self.playersByName[selectedPlayer])

            self._onPlayerChanged(event=None)

    def _loadConfiguration(self, event):
        self.configFile = self.configFileCtrl.GetValue().strip()
        if self.configFile:
            self.settings['SOD']['config'] = self.configFile
            with open(self.configFile, 'r') as f:
                self.configuration = json.load(f)
                self.studySelect.SetValue(self.configuration['tasks'][self.current]['base'])
        else:
            self.settings['activities']['config'] = ''

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
                ##########
#                gscript.run_command('r.unpack', input=new_path, overwrite=True, quiet=True)
#                name = os.path.basename(path).strip('.pack')
#                resultsToDisplay.put(name)
                ##########
                if os.path.basename(path).startswith('baseline'):
                    gscript.run_command('r.unpack', input=new_path, overwrite=True, quiet=True)
                    evt = ProcessBaseline(result='baseline')
                    wx.PostEvent(self, evt)
                else:
                    gscript.run_command('t.rast.import', input=new_path, output=os.path.basename(path) + '_imported', quiet=True, overwrite=True)
                    maps = gscript.read_command('t.rast.list', method='comma', input=os.path.basename(path) + '_imported').strip()
                    for each in maps.split(','):
                        resultsToDisplay.put(each)
                    evt = ProcessForDashboardEvent(result=each)
                    wx.PostEvent(self, evt)

                ##########
            elif message[0] == 'info':
                if message[1] == 'last':
                    name = message[2]
                    evt = ProcessForDashboardEvent(result=name)
                    wx.PostEvent(self, evt)

    def RunSimulation(self):
        if not self.baselineValues:
            dlg = wx.MessageDialog(self, 'Compute baseline first',
                                   'Missing baseline',
                                   wx.OK | wx.ICON_WARNING)
            dlg.ShowModal()
            dlg.Destroy()
            return

        self.infoBar.ShowMessage("Processing...")
        # grab a new raster of conditions
        # process new input layer
        treatment = 'treatment'
        studyArea = self.studySelect.GetValue()
        env = get_environment(raster=studyArea)
        species = self.configuration['SOD']['species']
        species_treated = self.configuration['SOD']['species_treated']
        all_trees = self.configuration['SOD']['all_trees']
        all_trees_treated = self.configuration['SOD']['all_trees_treated']

        # get max trees possible infected (actually 90prct)
        if not self.maxTrees:
            univar = gscript.parse_command('r.univar', map=species, flags='eg', env=env)
            self.maxTrees = float(univar['percentile_90'])

        gscript.mapcalc("{st} = if(isnull({tr}), {sp}, 0)".format(tr=treatment, sp=species, st=species_treated), env=env)
        # remove from all trees
        gscript.mapcalc("{att} = if(isnull({tr}), {at}, if ({at} - ({sp} - {st}) < 0, 1, {at} - ({sp} - {st})))".format(tr=treatment, at=all_trees, att=all_trees_treated, st=species_treated, sp=species), env=env)

        # get current player and attempt
        eventId = self.dashboard.get_current_event()
        playerId, playerName = self.dashboard.get_current_player()
        if not playerName:
            print 'no player selected'
            return

        self.playersCtrl.SetStringSelection(playerName)
        self.eventsCtrl.SetStringSelection(self.eventsByIds[eventId])
        attempts = []
        if self.bar:
            attempts = self.bar.getAllAttempts(playerName)
        if not attempts:
            new_attempt = '1'
            self.attemptCtrl.SetItems(['1'])
            self.attemptCtrl.SetStringSelection(new_attempt)
        else:
            self.attemptCtrl.SetItems([str(a) for a in attempts] + [str(max(attempts) + 1)])
            new_attempt = str(max(attempts) + 1)
            self.attemptCtrl.SetStringSelection(new_attempt)

        postfix = playerName + '_' + new_attempt
        # todo, save treatments
        gscript.run_command('g.copy', raster=[treatment, treatment + '_' + postfix])

        # run simulation
        message = 'cmd:start'
        message += ':output_series={}'.format(postfix)
        message += '|output={}'.format(postfix)
        message += '|species={}'.format(species_treated)
        message += '|lvtree={}'.format(all_trees_treated)
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
            gscript.write_command('r.colors', map=name, rules='-', stdin=self.GetInfColorTable(), quiet=True)
            cmd = ['d.rast', 'map={}'.format(name)]
            evt = addLayers(layerSpecs=[dict(ltype='raster', name=name, cmd=cmd, checked=True), ])
            self.scaniface.postEvent(self.scaniface, evt)

    def _computeBaseline(self):
        self.infoBar.ShowMessage("Computing baseline...")
        studyArea = self.studySelect.GetValue()
        extent = gscript.raster_info(studyArea)
        region = 'n={n},s={s},w={w},e={e}'.format(n=extent['north'], s=extent['south'], w=extent['west'], e=extent['east'])
        self.socket.sendall('cmd:baseline:' + region)

    def _loadBaseline(self):
        # load baseline from dashboard when starting
        self.baselineValues = []
        self.baselineScaledValues = []
        json = self.dashboard.get_baseline_barJson()
        if json:
            path = os.path.join(self.configuration['logDir'], 'barBaseline.json')
            self.barBaseline = BarData(filePath=path)
            self.barBaseline.setDataFromJson(json)
            self.baselineValues = self.barBaseline.getBaseline()
        json = self.dashboard.get_baseline_radarJson()
        if json:
            path = os.path.join(self.configuration['logDir'], 'radarBaseline.json')
            self.radarBaseline = RadarData(filePath=path)
            self.radarBaseline.setDataFromJson(json)
            self.baselineScaledValues = self.radarBaseline.getBaselineScaledValues()

    def _loadCharts(self):
        # load charts from dashboard when starting
        eventId = self.dashboard.get_current_event()
        json = self.dashboard.get_data_barJson(eventId)
        if json:
            path = os.path.join(self.configuration['logDir'], 'bar.json')
            self.bar = BarData(filePath=path)
            self.bar.setDataFromJson(json)

            playerName = self.playersCtrl.GetStringSelection()
            if playerName != wx.NOT_FOUND:
                attempts = self.bar.getAllAttempts(playerName)
                if attempts:
                    self.attemptCtrl.SetItems([str(a) for a in attempts])
                    self.attemptCtrl.SetStringSelection(str(max(attempts)))

        for playerId, playerName in self.playersByIds.iteritems():
            json = self.dashboard.get_data_radarJson(eventId, playerId)
            if json:
                path = os.path.join(self.configuration['logDir'], 'radar_{}.json'.format(playerName))
                self.radar[playerName] = RadarData(filePath=path)
                self.radar[playerName].setDataFromJson(json)

    def _processBaseline(self, event):
        self.infoBar.ShowMessage("Processing baseline...")
        env = get_environment(raster=event.result)
        res = gscript.raster_info(event.result)['nsres']
        infoBaseline = gscript.parse_command('r.univar', map=event.result, flags='g', env=env)
        all_trees = self.configuration['SOD']['all_trees']
        species = self.configuration['SOD']['species']
        infoAllTrees = gscript.parse_command('r.univar', map=all_trees, flags='g', env=env)
        # get max trees possible infected (actually 90prct)
        if not self.maxTrees:
            univar = gscript.parse_command('r.univar', map=species, flags='eg', env=env)
            self.maxTrees = float(univar['percentile_90'])

        n_dead = float(infoAllTrees['sum'])
        n_all_trees = float(infoAllTrees['sum'])
        perc_dead = n_dead / n_all_trees
        counts = gscript.read_command('r.stats', flags='c', input=event.result, env=env).strip().splitlines()
        zero, cnts = counts[0].split(' ')
        if zero == '0':
            infected_cells = int(infoBaseline['n']) - int(cnts)
        else:
            infected_cells = int(infoBaseline['n'])
        money = 0
        treated = 0
        price_per_tree = 0

        self.baselineValues = (n_dead, perc_dead, infected_cells * res * res / 10000, money, treated, price_per_tree)
        path = os.path.join(self.configuration['logDir'], 'radarBaseline.json')
        if not self.radarBaseline:
            self.radarBaseline = RadarData(filePath=path, baseline=self.baselineValues)
        self.dashboard.post_baseline_radar(path)
        path = os.path.join(self.configuration['logDir'], 'barBaseline.json')
        if not self.barBaseline:
            self.barBaseline = BarData(filePath=path, baseline=self.baselineValues)
        self.dashboard.post_baseline_bar(path)
        self.infoBar.Dismiss()

    def _processForDashboard(self, event):
        playerName = self.playersCtrl.GetStringSelection()
        playerId = self.playersByName[playerName]
        env = get_environment(raster=event.result)
        res = gscript.raster_info(event.result)['nsres']
        info = gscript.parse_command('r.univar', map=event.result, flags='g', env=env)
        all_trees = self.configuration['SOD']['all_trees']
        infoAllTrees = gscript.parse_command('r.univar', map=all_trees, flags='g', env=env)
        n_dead = float(info['sum'])
        n_all_trees = float(infoAllTrees['sum'])
        perc_dead = n_dead / n_all_trees
        counts = gscript.read_command('r.stats', flags='c', input=event.result, env=env).strip().splitlines()
        zero, cnts = counts[0].split(' ')
        if zero == '0':
            infected_cells = int(info['n']) - int(cnts)
        else:
            infected_cells = int(info['n'])
        money = 0
        treated = 0
        price_per_tree = 0

        record = (n_dead, perc_dead, infected_cells * res * res / 10000, money, treated, price_per_tree)
        radarValues = [10, 0, 10, 0, 10, 10]

        path = os.path.join(self.configuration['logDir'], 'radar_{}.json'.format(playerName))
        if playerName not in self.radar:
            self.radar[playerName] = RadarData(filePath=path, baseline=self.baselineValues)
        self.radar[playerName].addRecord(radarValues, record, baseline=False)
        self.dashboard.post_data_radar(jsonfile=path, eventId=self.dashboard.get_current_event(), playerId=playerId)

        path = os.path.join(self.configuration['logDir'], 'bar.json')  # maybe named with event
        if not self.bar:
            self.bar = BarData(filePath=path, baseline=self.baselineValues)
        self.bar.addRecord(record, playerName)
        self.dashboard.post_data_bar(jsonfile=path, eventId=self.dashboard.get_current_event())
        self.infoBar.Dismiss()

    def OnClose(self, event):
        # timer stop
        if self.timer.IsRunning():
            self.timer.Stop()
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

    def _stopScanning(self):
        self.scaniface.pause = True
        self.scaniface.changedInput = True

    def _startScanning(self):
        self.scaniface.pause = False
        self.scaniface.changedInput = True

    def StartTreatment(self, event):
        self.scaniface.additionalParams4Analyses = {}
        self.LoadLayers()
        treatmentRaster = self.treatmentSelect.GetValue()
        if treatmentRaster:
            self.giface.GetMapWindow().ZoomToMap(layers=[treatmentRaster])
            self.settings['scan']['elevation'] = treatmentRaster
        else:
            self.settings['scan']['elevation'] = self.tasks[self.current]['base']

        self.settings['analyses']['file'] = os.path.join(self.configuration['taskDir'], self.tasks[self.current]['analyses'])
        self.settings['output']['scan'] = 'scan'
        if 'scanning_params' in self.tasks[self.current]:
            for each in self.tasks[self.current]['scanning_params'].keys():
                self.settings['scan'][each] = self.tasks[self.current]['scanning_params'][each]
        # resume scanning
        if 'filter' in self.tasks[self.current]:
            self.scaniface.filter['filter'] = True
            self.scaniface.filter['counter'] = 0
            self.scaniface.filter['threshold'] = self.tasks[self.current]['filter']['threshold']
            self.scaniface.filter['debug'] = self.tasks[self.current]['filter']['debug']
        if 'single_scan' in self.tasks[self.current] and self.tasks[self.current]['single_scan']:
            self._stopScanning()
        else:
            self._startScanning()
        # profile
        if 'profile' in self.tasks[self.current]:
            self.StartProfile()
        # display
        if 'display' in self.tasks[self.current]:
            self.StartDisplay()

    def StopTreatment(self, event):
        def _closeAdditionalWindows(self):
            if self.profileFrame:
                self.profileFrame.Close()
                self.profileFrame = None
            if self.dashboardFrame:
                self.dashboardFrame.Destroy()
                self.dashboardFrame = None

        def _removeAllLayers(self):
            ll = self.giface.GetLayerList()
            for l in reversed(ll):
                ll.DeleteLayer(l)

        self._closeAdditionalWindows()
        self._removeAllLayers()
        self.settings['analyses']['file'] = ''
        self._stopScanning()

    def _bindButtons(self):
        topParent = wx.GetTopLevelParent(self)
        if "keyboard_events" in self.configuration:
            items = []
            if 'simulate' in self.configuration['keyboard_events']:
                simulateId = wx.NewId()
                items.append((wx.ACCEL_NORMAL, self.configuration['keyboard_events']['simulate'], simulateId))
                topParent.Bind(wx.EVT_MENU, lambda evt: self.RunSimulation(), id=simulateId)
            accel_tbl = wx.AcceleratorTable(items)
            topParent.SetAcceleratorTable(accel_tbl)
            # Map displays
            for mapw in self.giface.GetAllMapDisplays():
                mapw.Bind(wx.EVT_MENU, lambda evt: self.RunSimulation(), id=simulateId)
                mapw.SetAcceleratorTable(accel_tbl)
            # Layer Manager
            lm = self.giface.lmgr
            lm.Bind(wx.EVT_MENU, lambda evt: self.RunSimulation(), id=simulateId)
            lm.SetAcceleratorTable(accel_tbl)

    def LoadLayers(self, zoomToLayers=True):
        ll = self.giface.GetLayerList()
        zoom = []
        for i, cmd in enumerate(self.tasks[self.current]['layers']):
            opacity = 1.0
            if "layers_opacity" in self.tasks[self.current]:
                opacity = float(self.tasks[self.current]['layers_opacity'][i])
            if cmd[0] == 'd.rast':
                l = ll.AddLayer('raster', name=cmd[1].split('=')[1], checked=True,
                                opacity=opacity, cmd=cmd)
                if cmd[1].split('=')[1] != 'scan':
                    zoom.append(l.maplayer)
            elif cmd[0] == 'd.vect':
                ll.AddLayer('vector', name=cmd[1].split('=')[1], checked=True,
                            opacity=opacity, cmd=cmd)
            else:
                ll.AddLayer('command', name=' '.join(cmd), checked=True,
                            opacity=opacity, cmd=[])

        if zoomToLayers:
            self.giface.GetMapWindow().ZoomToMap(layers=zoom)

    def GetInfColorTable(self):
        color = ['0 200:200:200',
                 '{} yellow'.format(0.5 * self.maxTrees),
                 '{} orange'.format(0.7 * self.maxTrees),
                 '{} red'.format(0.8 * self.maxTrees),
                 '{} 200:0:0'.format(self.maxTrees),
                 '{} 0:0:0'.format(2 * self.maxTrees)]
        return '\n'.join(color)
