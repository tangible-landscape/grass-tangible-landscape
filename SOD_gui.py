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
import re
import wx
import wx.lib.newevent
import wx.lib.filebrowsebutton as filebrowse

from gui_core.gselect import Select
import grass.script as gscript
from grass.pydispatch.signal import Signal

from tangible_utils import addLayers, get_environment, removeLayers

from SOD_dashboard import DashBoardRequests, RadarData, BarData
from activities_dashboard import DashboardFrame, MultipleDashboardFrame


ProcessForDashboardEvent, EVT_PROCESS_NEW_EVENT = wx.lib.newevent.NewEvent()
ProcessBaseline, EVT_PROCESS_BASELINE_NEW_EVENT = wx.lib.newevent.NewEvent()
updateDisplay, EVT_UPDATE_DISPLAY = wx.lib.newevent.NewEvent()
updateTimeDisplay, EVT_UPDATE_TIME_DISPLAY = wx.lib.newevent.NewEvent()

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
        self._currentlyRunning = False
        self.switchCurrentResult = 0
        self.showDisplayChange = True
        self.lastRecordedTreatment = ''

        self.dashboard = DashBoardRequests()
        self.radarBaseline = None
        self.barBaseline = None
        self.bar = None
        self.radar = {}

        self.profileFrame = self.dashboardFrame = self.timeDisplay = None

        self.treated_area = 0
        self.money_spent = 0
        self.price_per_m2 = 1.24

        if 'SOD' not in self.settings:
            self.settings['SOD'] = {}
            self.settings['SOD']['config'] = ''
            self.settings['SOD']['urlDashboard'] = ''
            self.settings['SOD']['urlSteering'] = ''
        else:
            self.configFile = self.settings['SOD']['config']


        self.infoBar = wx.InfoBar(self)
        self.urlDashboard = wx.TextCtrl(self, value=self.settings['SOD']['urlDashboard'])
        self.urlSteering = wx.TextCtrl(self, value=self.settings['SOD']['urlSteering'])
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
        baselineButton.Bind(wx.EVT_BUTTON, lambda evt: self.ComputeBaseline())
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
                    self.speed = int(self.configuration['SOD']['animation_speed'])
            except IOError:
                self.configFile = None

        self._bindButtons()

        self.Bind(EVT_UPDATE_DISPLAY, self.OnDisplayUpdate)
        self.Bind(EVT_UPDATE_TIME_DISPLAY, self.OnTimeDisplayUpdate)

    def _connect(self):
        self._connectDashboard()
        self._connectSteering()
        self._loadBaseline()
        self._loadCharts()
        self._bindButtons()

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
            eventId = self.dashboard.get_current_event()
            if eventId:
                self.eventsCtrl.SetStringSelection(self.eventsByIds[eventId])
            else:
                self.eventsCtrl.SetSelection(0)
            self.playersByIds = dict(zip(*self.dashboard.get_players(self.eventsByName[self.eventsCtrl.GetStringSelection()])))
            self.playersByName = dict(reversed(item) for item in self.playersByIds.items())
            self.playersCtrl.SetItems(self.playersByIds.values())
            playerId, name = self.dashboard.get_current_player()
            if playerId:
                self.playersCtrl.SetStringSelection(name)
            else:
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

    def OnDisplayUpdate(self, event):
        if not self.dashboardFrame:
            return
        if self.showDisplayChange:
            self.dashboardFrame.show_value(event.value)

    def OnTimeDisplayUpdate(self, event):
        if not self.timeDisplay:
            return
        self.timeDisplay.Update(event.value)


    def DeleteAttempt(self):
        event = self.eventsCtrl.GetStringSelection()
        selectedPlayer = self.playersCtrl.GetStringSelection()
        attempt = self.attemptCtrl.GetStringSelection()
        if attempt != wx.NOT_FOUND:
            if self.bar:
                self.bar.removeAttempt(selectedPlayer, int(attempt))
                jsonfile = os.path.join(self.configuration['logDir'], 'bar_{e}.json'.format(e=event))
                self.dashboard.post_data_bar(jsonfile=jsonfile, eventId=self.eventsByName[event])
            if self.radar:
                self.radar[selectedPlayer].removeAttempt(int(attempt))
                jsonfile = os.path.join(self.configuration['logDir'], 'radar_{p}_{e}.json'.format(p=selectedPlayer, e=event))
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
                if not os.path.exists(TMP_DIR):
                    os.mkdir(TMP_DIR)
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
                    #gscript.run_command('t.rast.import', input=new_path, output=os.path.basename(path) + '_imported', quiet=True, overwrite=True)
                    #maps = gscript.read_command('t.rast.list', method='comma', input=os.path.basename(path) + '_imported').strip()
                    #for each in maps.split(','):
                    #    resultsToDisplay.put(each)
                    #evt = ProcessForDashboardEvent(result=each)
                    #wx.PostEvent(self, evt)
                    gscript.run_command('r.unpack', input=new_path, overwrite=True, quiet=True)
                    name = os.path.basename(path).strip('.pack')
                    # avoid showing aggregate result
                    if len(name.split('_')) == 6 or len(name.split('_')) == 7:
                        resultsToDisplay.put(name)
                        print 'display'

                ##########
            elif message[0] == 'info':
                if message[1] == 'last':
                    name = message[2]
                    evt = ProcessForDashboardEvent(result=name)
                    wx.PostEvent(self, evt)

    def ShowResults(self, event=None):
        # clear the queue to stop animation
        with self.resultsToDisplay.mutex:
            self.resultsToDisplay.queue.clear()

        if self.switchCurrentResult == 0:
            self.ShowAnimation()
        elif self.switchCurrentResult == 1:
            self.ShowProbability()
        elif self.switchCurrentResult == 2:
            self.RemoveAllResultsLayers()
            self.showDisplayChange = True

        self.switchCurrentResult += 1
        if self.switchCurrentResult >= 3:
            self.switchCurrentResult = 0

    def ShowAnimation(self, event=None):
        event = self.eventsCtrl.GetStringSelection()
        name = self.playersCtrl.GetStringSelection()
        attempt = self.attemptCtrl.GetStringSelection()
        self.AddLayersAsAnimation(etype='raster', pattern="{n}_{a}_{e}_*".format(n=name, e=event, a=attempt))

    def ShowProbability(self, event=None):
        event = self.eventsCtrl.GetStringSelection()
        name = self.playersCtrl.GetStringSelection()
        attempt = self.attemptCtrl.GetStringSelection()
        name = self.configuration['SOD']['probability'] + '_' + name + '_' + attempt + '_' + event

        gscript.run_command('r.colors', map=name, quiet=True,
                            rules=os.path.join(self.configuration['taskDir'], self.configuration['SOD']['color_probability']))
        cmd = ['d.rast','values=0-10', 'flags=i', 'map={}'.format(name)]
        self.RemoveAllResultsLayers()
        self.ShowTreatment()
        ll = self.giface.GetLayerList()
        ll.AddLayer('raster', name=name, checked=True, opacity=1, cmd=cmd)

    def ShowTreatment(self, event=None):
        event = self.eventsCtrl.GetStringSelection()
        name = self.playersCtrl.GetStringSelection()
        attempt = self.attemptCtrl.GetStringSelection()
        name = self.configuration['SOD']['treatments'] + '_' + name + '_' + attempt + '_' + event

        env = get_environment(raster=name)
        gscript.run_command('r.to.vect', flags='st', input=name, output=name, type='area', env=env)
        gscript.run_command('v.generalize', input=name, output=name + '_gen', method='snakes', threshold=10, env=env)
        cmd = ['d.vect', 'map={}'.format(name + '_gen'), 'color=none', 'fill_color=144:238:144']
        ll = self.giface.GetLayerList()
        ll.AddLayer('vector', name=name + '_gen', checked=True, opacity=1, cmd=cmd)

    def _RunSimulation(self, event=None):
        print '_runSimulation'
        if self.switchCurrentResult == 0:
            #it's allowed to interact now
            # just to be sure remove results
            self.RemoveAllResultsLayers()
            wx.FutureCall(self.configuration['SOD']['waitBeforeRun'], self.RunSimulation)

    def RunSimulation(self, event=None):
        print 'run simulation'
        if not self.baselineValues:
            dlg = wx.MessageDialog(self, 'Compute baseline first',
                                   'Missing baseline',
                                   wx.OK | wx.ICON_WARNING)
            dlg.ShowModal()
            dlg.Destroy()
            return

        if self._currentlyRunning:
            return

        self.showDisplayChange = False

        self._currentlyRunning = True
        self.infoBar.ShowMessage("Processing...")
        # grab a new raster of conditions
        # process new input layer
        treatments = self.configuration['SOD']['treatments']
        treatments_resampled = treatments + '_resampled'
        studyArea = self.studySelect.GetValue()
        if not studyArea:
            studyArea = self.configuration['tasks'][self.current]['base']
        species = self.configuration['SOD']['species']
        infected = self.configuration['SOD']['infected']
        species_treated = self.configuration['SOD']['species_treated']
        all_trees = self.configuration['SOD']['all_trees']
        all_trees_treated = self.configuration['SOD']['all_trees_treated']
        inf_treated = self.configuration['SOD']['infected_treated']
        probability = self.configuration['SOD']['probability']
        env = get_environment(raster=studyArea, align=species)

        gscript.run_command('r.resamp.stats', input=treatments, output=treatments_resampled, flags='w', method='count', env=env)
        maxvalue = gscript.raster_info(treatments_resampled)['max']
        univar = gscript.parse_command('r.univar', flags='g', map=treatments_resampled, env=env)
        self.treated_area = (float(univar['sum']) / maxvalue) * 10000
        self.money_spent = self.treated_area * self.price_per_m2
#        gscript.mapcalc("{s} = {l} - {l} * ({t} / {m})".format(s=species_treated, t=treatments_resampled,
#                                                               m=maxvalue, l=species), env=env)
        gscript.mapcalc("{s} = int(if ({i} == 0, {l} - {l} * ({t} / {m}), max(1, {l} - {l} * ({t} / {m}))))".format(s=species_treated, t=treatments_resampled,
                                                               i=infected, m=maxvalue, l=species), env=env)
        gscript.mapcalc("{ni} = min({i}, {st})".format(i=infected, st=species_treated, ni=inf_treated), env=env)
#        gscript.mapcalc("{att} = if(isnull({tr}), {at}, if ({at} - ({sp} - {st}) < 0, 1, {at} - ({sp} - {st})))".format(tr=treatments,
#                        at=all_trees, att=all_trees_treated, st=species_treated, sp=species), env=env)
        gscript.mapcalc("{att} = round({at} - ({s} - {st}))".format(at=all_trees, att=all_trees_treated, st=species_treated, s=species), env=env)

        # get current player and attempt
        eventId = self.dashboard.get_current_event()
        playerId, playerName = self.dashboard.get_current_player()
        if not playerName:
            print 'no player selected'
            return

        self.eventsCtrl.SetStringSelection(self.eventsByIds[eventId])
        self._onEventChanged(event=None)
        self.playersCtrl.SetStringSelection(playerName)
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

        postfix = playerName + '_' + new_attempt + '_' + self.eventsByIds[eventId]
        probability = probability + '_' + postfix
        # todo, save treatments
        gscript.run_command('g.copy', raster=[treatments, treatments + '_' + postfix], env=env)
        self.lastRecordedTreatment = treatments + '_' + postfix
        extent = gscript.raster_info(studyArea)
        region = '{n},{s},{w},{e},{a}'.format(n=extent['north'], s=extent['south'],
                                              w=extent['west'], e=extent['east'], a=species)
        # run simulation
        message = 'cmd:start'
        message += ':output_series={}'.format(postfix)
        message += '|output={}'.format(postfix)
        message += '|region={}'.format(region)
        message += '|species={}'.format(species_treated)
        message += '|probability={}'.format(probability)
        message += '|lvtree={}'.format(all_trees_treated)
        message += '|start_time={}'.format(self.configuration['SOD']['start_time'])
        message += '|end_time={}'.format(self.configuration['SOD']['end_time'])
        message += '|kappa={}'.format(self.configuration['SOD']['kappa'])
        message += '|spore_rate={}'.format(self.configuration['SOD']['spore_rate'])
        message += '|wind={}'.format(self.configuration['SOD']['wind'])
        message += '|infected={}'.format(self.configuration['SOD']['infected'])
        message += '|runs={}'.format(self.configuration['SOD']['runs'])

        self.RemoveAllResultsLayers()

        self.socket.sendall(message)

    def _run(self):
        self.socket.sendall('cmd:play')

    def _stop(self):
        self.socket.sendall('cmd:end')


    def _displayResult(self, event):
        if not self.resultsToDisplay.empty():
            name = self.resultsToDisplay.get()
            gscript.run_command('r.colors', map=name, quiet=True,
                                rules=os.path.join(self.configuration['taskDir'], self.configuration['SOD']['color_trees']))
            cmd = ['d.rast','values=0', 'flags=i', 'map={}'.format(name)]
            evt = addLayers(layerSpecs=[dict(ltype='raster', name=name, cmd=cmd, checked=True), ])
            self.scaniface.postEvent(self.scaniface, evt)
            # update year
            res = re.search("_20[0-9]{2}_", name)
            if res:
                year = res.group().strip('_')
                evt2 = updateTimeDisplay(value=year)
                self.scaniface.postEvent(self, evt2)

    def ComputeBaseline(self):
        self.infoBar.ShowMessage("Computing baseline...")
        studyArea = self.studySelect.GetValue()
        if not studyArea:
            studyArea = self.configuration['tasks'][self.current]['base']
        extent = gscript.raster_info(studyArea)
        species = self.configuration['SOD']['species']
        region = '{n},{s},{w},{e},{a}'.format(n=extent['north'], s=extent['south'],
                                              w=extent['west'], e=extent['east'], a=species)
        message = 'cmd:baseline'
        message += ':region={}'.format(region)
        message += '|output={}'.format(self.configuration['SOD']['baseline'])
        message += '|probability={}'.format(self.configuration['SOD']['baseline_probability'])
        message += '|species={}'.format(self.configuration['SOD']['species'])
        message += '|lvtree={}'.format(self.configuration['SOD']['all_trees'])
        message += '|start_time={}'.format(self.configuration['SOD']['start_time'])
        message += '|end_time={}'.format(self.configuration['SOD']['end_time'])
        message += '|spore_rate={}'.format(self.configuration['SOD']['spore_rate'])
        message += '|kappa={}'.format(self.configuration['SOD']['kappa'])
        message += '|wind={}'.format(self.configuration['SOD']['wind'])
        message += '|infected={}'.format(self.configuration['SOD']['infected'])
        message += '|runs={}'.format(self.configuration['SOD']['runs_baseline'])
        self.socket.sendall(message)

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
        if not eventId:
            return
        eventName = self.eventsByIds[eventId]
        json = self.dashboard.get_data_barJson(eventId)
        if json:
            path = os.path.join(self.configuration['logDir'], 'bar_{e}.json'.format(e=eventName))
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
                path = os.path.join(self.configuration['logDir'], 'radar_{p}_{e}.json'.format(p=playerName, e=eventName))
                self.radar[playerName] = RadarData(filePath=path)
                self.radar[playerName].setDataFromJson(json)

    def _processBaseline(self, event):
        self.infoBar.ShowMessage("Processing baseline...")
        print "processing baseline in GUI"
        env = get_environment(raster=event.result)
        res = gscript.raster_info(event.result)['nsres']
        infoBaseline = gscript.parse_command('r.univar', map=event.result, flags='g', env=env)
        species = self.configuration['SOD']['species']
        infoAllTanoaks = gscript.parse_command('r.univar', map=species, flags='g', env=env)

        n_dead = float(infoBaseline['sum'])
        n_all_tanoaks = float(infoAllTanoaks['sum'])
        perc_dead = n_dead / n_all_tanoaks
        counts = gscript.read_command('r.stats', flags='c', input=event.result, env=env).strip().splitlines()
        zero, cnts = counts[0].split(' ')
        if zero == '0':
            infected_cells = int(infoBaseline['n']) - int(cnts)
        else:
            infected_cells = int(infoBaseline['n'])
        money = 0
        treated = 0
        price_per_tree = 0

        gscript.run_command('r.colors', map=event.result, quiet=True,
                            rules=os.path.join(self.configuration['taskDir'], self.configuration['SOD']['color_trees']))
        self.baselineValues = (n_dead, perc_dead, infected_cells * res * res / 10000, money, treated, price_per_tree)
        path = os.path.join(self.configuration['logDir'], 'radarBaseline.json')
        self.radarBaseline = RadarData(filePath=path, baseline=self.baselineValues)
        self.dashboard.post_baseline_radar(path)
        path = os.path.join(self.configuration['logDir'], 'barBaseline.json')
        self.barBaseline = BarData(filePath=path, baseline=self.baselineValues)
        self.dashboard.post_baseline_bar(path)
        self.infoBar.Dismiss()

    def _processForDashboard(self, event):
        playerName = self.playersCtrl.GetStringSelection()
        playerId = self.playersByName[playerName]
        eventName = self.eventsCtrl.GetStringSelection()
        env = get_environment(raster=event.result)
        res = gscript.raster_info(event.result)['nsres']
        info = gscript.parse_command('r.univar', map=event.result, flags='g', env=env)
        all_tanoaks = self.configuration['SOD']['species']
        infoAllTanoaks = gscript.parse_command('r.univar', map=all_tanoaks, flags='g', env=env)
        n_dead = float(info['sum'])
        n_all_tanoaks = float(infoAllTanoaks['sum'])
        perc_dead = n_dead / n_all_tanoaks
        counts = gscript.read_command('r.stats', flags='c', input=event.result, env=env).strip().splitlines()
        zero, cnts = counts[0].split(' ')
        if zero == '0':
            infected_cells = int(info['n']) - int(cnts)
        else:
            infected_cells = int(info['n'])
        money = self.money_spent
        treated = self.treated_area


        data = gscript.read_command('r.univar', flags='gt', map=all_tanoaks, zones=self.lastRecordedTreatment).strip().splitlines()[-1].split('|')
        culled_trees = int(data[-1])
        print 'culled_trees', culled_trees
        price_per_tree = self.money_spent / (self.baselineValues[0] - n_dead - culled_trees)

        record = (n_dead, perc_dead, infected_cells * res * res / 10000, money, treated, price_per_tree)
        # scaling radar values
        n_dead_scaled = round(min(10 * n_dead / float(self.baselineValues[0]), 10))
        perc_dead_scaled = round(min(10 * perc_dead / float(self.baselineValues[1]), 10))
        infected_scaled = round(min(10 * record[2] / float(self.baselineValues[2]), 10))
        max_money = 5000000.
        money_scaled = round(min(10 * record[3] / max_money, 10))
        treated_scaled = round(min(10 * record[4] / (max_money / 1.24), 10))
        # $50 max?
        price_per_tree_scaled = round(max(min(10 * record[5] / 50, 10), 0))
        radarValues = [n_dead_scaled, perc_dead_scaled, infected_scaled, money_scaled, treated_scaled, price_per_tree_scaled]

        path = os.path.join(self.configuration['logDir'], 'radar_{p}_{e}.json'.format(p=playerName, e=eventName))
        if playerName not in self.radar:
            self.radar[playerName] = RadarData(filePath=path, baseline=self.baselineValues)
        self.radar[playerName].addRecord(radarValues, record, baseline=False)
        self.dashboard.post_data_radar(jsonfile=path, eventId=self.dashboard.get_current_event(), playerId=playerId)

        path = os.path.join(self.configuration['logDir'], 'bar_{e}.json'.format(e=eventName))  # maybe named with event
        if not self.bar:
            self.bar = BarData(filePath=path, baseline=self.baselineValues)
        self.bar.addRecord(record, playerName)
        self.dashboard.post_data_bar(jsonfile=path, eventId=self.dashboard.get_current_event())
        self.infoBar.Dismiss()
        self._currentlyRunning = False
        self.switchCurrentResult = 1
        #print 'remove layers'
#        # TODO remove all layers

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

    def StartTreatment(self):
        self.showDisplayChange = True
        self.switchCurrentResult = 0
        self.scaniface.additionalParams4Analyses = {}
        self.LoadLayers()
        treatmentRaster = self.treatmentSelect.GetValue()
        if treatmentRaster:
            self.giface.GetMapWindow().ZoomToMap(layers=[treatmentRaster])
            self.settings['scan']['elevation'] = treatmentRaster
        else:
            self.settings['scan']['elevation'] = self.configuration['tasks'][self.current]['base']

        self.settings['analyses']['file'] = os.path.join(self.configuration['taskDir'], self.configuration['tasks'][self.current]['analyses'])
        self.settings['output']['scan'] = 'scan'
        if 'scanning_params' in self.configuration['tasks'][self.current]:
            for each in self.configuration['tasks'][self.current]['scanning_params'].keys():
                self.settings['scan'][each] = self.configuration['tasks'][self.current]['scanning_params'][each]
        # resume scanning
        if 'filter' in self.configuration['tasks'][self.current]:
            self.scaniface.filter['filter'] = True
            self.scaniface.filter['counter'] = 0
            self.scaniface.filter['threshold'] = self.configuration['tasks'][self.current]['filter']['threshold']
            self.scaniface.filter['debug'] = self.configuration['tasks'][self.current]['filter']['debug']
        if 'single_scan' in self.configuration['tasks'][self.current] and self.configuration['tasks'][self.current]['single_scan']:
            self._stopScanning()
        else:
            self._startScanning()
        # profile
        if 'profile' in self.configuration['tasks'][self.current]:
            self.StartProfile()
        # display
        if 'display' in self.configuration['tasks'][self.current]:
            self.StartDisplay()
        # time display
        if 'time_display' in self.configuration['tasks'][self.current]:
            self.StartTimeDisplay()
        # start display timer
        self.timer.Start(self.speed)

    def StopTreatment(self):
        def _closeAdditionalWindows():
            if self.profileFrame:
                self.profileFrame.Close()
                self.profileFrame = None
            if self.dashboardFrame:
                self.dashboardFrame.Destroy()
                self.dashboardFrame = None
            if self.timeDisplay:
                self.timeDisplay.Destroy()
                self.timeDisplay = None

        def _removeAllLayers():
            ll = self.giface.GetLayerList()
            for l in reversed(ll):
                ll.DeleteLayer(l)

        _closeAdditionalWindows()
        _removeAllLayers()
        self.settings['analyses']['file'] = ''
        self._stopScanning()
        self.timer.Stop()

    def _bindButtons(self):
        topParent = wx.GetTopLevelParent(self)
        if "keyboard_events" in self.configuration:
            items = []
            simulateId = animateId = None
            if 'simulate' in self.configuration['keyboard_events']:
                simulateId = wx.NewId()
                items.append((wx.ACCEL_NORMAL, self.configuration['keyboard_events']['simulate'], simulateId))
                topParent.Bind(wx.EVT_MENU, self._RunSimulation, id=simulateId)
            if 'animate' in self.configuration['keyboard_events']:
                animateId = wx.NewId()
                items.append((wx.ACCEL_NORMAL, self.configuration['keyboard_events']['animate'], animateId))
                topParent.Bind(wx.EVT_MENU, self.ShowResults, id=animateId)
            accel_tbl = wx.AcceleratorTable(items)
            topParent.SetAcceleratorTable(accel_tbl)
            # Map displays
            for mapw in self.giface.GetAllMapDisplays():
                if simulateId:
                    mapw.Bind(wx.EVT_MENU, self._RunSimulation, id=simulateId)
                if animateId:
                    mapw.Bind(wx.EVT_MENU, self.ShowResults, id=animateId)
                mapw.SetAcceleratorTable(accel_tbl)
            # Layer Manager
            lm = self.giface.lmgr
            if simulateId:
                lm.Bind(wx.EVT_MENU, self._RunSimulation, id=simulateId)
            if animateId:
                lm.Bind(wx.EVT_MENU, self.ShowResults, id=animateId)
            lm.SetAcceleratorTable(accel_tbl)

    def LoadLayers(self, zoomToLayers=True):
        ll = self.giface.GetLayerList()
        zoom = []
        for i, cmd in enumerate(self.configuration['tasks'][self.current]['layers']):
            opacity = 1.0
            if "layers_opacity" in self.configuration['tasks'][self.current]:
                opacity = float(self.configuration['tasks'][self.current]['layers_opacity'][i])
            if cmd[0] == 'd.rast':
                l = ll.AddLayer('raster', name=cmd[1].split('=')[1], checked=True,
                                opacity=opacity, cmd=cmd)
                if cmd[1].split('=')[1] != 'scan':
                    zoom.append(l.maplayer)
            elif cmd[0] == 'd.vect':
                ll.AddLayer('vector', name=cmd[1].split('=')[1], checked=True,
                            opacity=opacity, cmd=cmd)
            elif cmd[0] == 'd.labels':
                ll.AddLayer('labels', name=cmd[1].split('=')[1], checked=True,
                            opacity=opacity, cmd=cmd)
            else:
                ll.AddLayer('command', name=' '.join(cmd), checked=True,
                            opacity=opacity, cmd=[])

        if zoomToLayers:
            self.giface.GetMapWindow().ZoomToMap(layers=zoom)

    def RemoveAllResultsLayers(self):
        event = self.eventsCtrl.GetStringSelection()
        pattern_layers_r = gscript.list_grouped(type='raster', pattern="*{}*".format(event))[gscript.gisenv()['MAPSET']]
        pattern_layers_v = gscript.list_grouped(type='vector', pattern="*{}*".format(event))[gscript.gisenv()['MAPSET']]
        self.RemoveLayers(layers=pattern_layers_r + pattern_layers_v)

    def RemoveLayers(self, etype='raster', pattern=None, layers=None):
        all_layers = []
        if pattern:
            pattern_layers = gscript.list_grouped(type=etype, pattern=pattern)[gscript.gisenv()['MAPSET']]
            all_layers += pattern_layers
        if layers:
            all_layers += layers
        ll = self.giface.GetLayerList()
        for l in reversed(ll):
            name = l.maplayer.name.split('@')[0]
            if name in all_layers:
                ll.DeleteLayer(l)

    def AddLayersAsAnimation(self, etype='raster', pattern=None, layers=None):
        all_layers = []
        if pattern:
            pattern_layers = gscript.list_grouped(type=etype, pattern=pattern)[gscript.gisenv()['MAPSET']]
            all_layers += pattern_layers
        if layers:
            all_layers += layers

        self.RemoveAllResultsLayers()
        self.ShowTreatment()
        for name in all_layers:
            self.resultsToDisplay.put(name)

    def StartDisplay(self):
        multiple = False if 'multiple' not in self.configuration['tasks'][self.current]['display'] else self.configuration['tasks'][self.current]['display']['multiple']
        title = None if 'title' not in self.configuration['tasks'][self.current]['display'] else self.configuration['tasks'][self.current]['display']['title']
        fontsize = self.configuration['tasks'][self.current]['display']['fontsize']
        average = self.configuration['tasks'][self.current]['display']['average']
        maximum = self.configuration['tasks'][self.current]['display']['maximum']
        formatting_string = self.configuration['tasks'][self.current]['display']['formatting_string']
        if multiple:
            self.dashboardFrame = MultipleDashboardFrame(self, fontsize=fontsize, average=average, maximum=maximum,
                                                     title=title, formatting_string=formatting_string)
        else:
            self.dashboardFrame = DashboardFrame(self, fontsize=fontsize, average=average, maximum=maximum, title=title, formatting_string=formatting_string)
        pos = self.configuration['tasks'][self.current]['display']['position']
        size = self.configuration['tasks'][self.current]['display']['size']
        self.dashboardFrame.SetSize(size)
        self.dashboardFrame.Show()
        self.dashboardFrame.SetPosition(pos)

    def StartTimeDisplay(self):
        self.timeDisplay = TimeDisplay(self, fontsize=self.configuration['tasks'][self.current]['time_display']['fontsize'])
        pos = self.configuration['tasks'][self.current]['time_display']['position']
        size = self.configuration['tasks'][self.current]['time_display']['size']
        self.timeDisplay.SetSize(size)
        self.timeDisplay.Show()
        self.timeDisplay.SetPosition(pos)

class TimeDisplay(wx.Frame):
    def __init__(self, parent, fontsize):
        wx.Frame.__init__(self, parent, style=wx.NO_BORDER)
        self.label = wx.StaticText(self, style=wx.ALIGN_CENTRE_HORIZONTAL)
        font = wx.Font(fontsize, wx.DEFAULT, wx.NORMAL, wx.BOLD)
        self.label.SetFont(font)
        self.sizer = wx.BoxSizer(wx.VERTICAL)
        self.sizer.Add(self.label, 1, wx.ALL|wx.ALIGN_CENTER|wx.GROW, border=10)
        self.SetSizer(self.sizer)
        self.sizer.Fit(self)

    def Update(self, value):
        self.label.SetLabel(str(value))
