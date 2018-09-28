# -*- coding: utf-8 -*-
"""
@brief POPS GUI

This program is free software under the GNU General Public License
(>=v2). Read the file COPYING that comes with GRASS for details.

@author: Anna Petrasova (akratoc@ncsu.edu)
"""
import os
import socket
import threading
import Queue
import traceback
import json
import imp
import re
import wx
import wx.lib.newevent
import wx.lib.filebrowsebutton as filebrowse

from gui_core.gselect import Select
import grass.script as gscript
from grass.pydispatch.signal import Signal
from grass.exceptions import CalledModuleError, ScriptError

from tangible_utils import addLayers, get_environment, removeLayers, checkLayers

from pops_dashboard import DashBoardRequests, RadarData, BarData
from activities_dashboard import DashboardFrame, MultipleDashboardFrame


ProcessForDashboardEvent, EVT_PROCESS_NEW_EVENT = wx.lib.newevent.NewEvent()
ProcessBaseline, EVT_PROCESS_BASELINE_NEW_EVENT = wx.lib.newevent.NewEvent()
updateDisplay, EVT_UPDATE_DISPLAY = wx.lib.newevent.NewEvent()
updateTimeDisplay, EVT_UPDATE_TIME_DISPLAY = wx.lib.newevent.NewEvent()

TMP_DIR = '/tmp/test_SOD/'


class PopsPanel(wx.Panel):
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
        self.playersByIds = self.playersByName = None
        self.eventsByIds = self.eventsByName = None
        self.configFile = ''
        self.configuration = {}
        self.current = 0
        self.baselineEnv = None
        self._currentlyRunning = False
        self.switchCurrentResult = 0
        self.showDisplayChange = True
        self.lastRecordedTreatment = ''
        self.lastDisplayedLayerAnim = ''

        self.dashboard = None
        self.baselineValues = []
        self.scenarios = {}
        self.radarBaseline = None
        self.barBaseline = None
        self.bar = None
        self.radar = {}

        self.profileFrame = self.dashboardFrame = self.timeDisplay = None

        self.treated_area = 0
        self.money_spent = 0

        if 'POPS' not in self.settings:
            self.settings['POPS'] = {}
            self.settings['POPS']['config'] = ''
        else:
            self.configFile = self.settings['POPS']['config']
            
            
        if self.configFile:
            try:
                with open(self.configFile, 'r') as f:
                    self.configuration = json.load(f)
                    # this should reset the analysis file only when configuration is successfully loaded
                    self.settings['analyses']['file'] = ''
                    self.speed = int(self.configuration['POPS']['animation_speed'])
            except IOError:
                self.configFile = ''

        dashBox = wx.StaticBox(self, wx.ID_ANY, "Dashboard")
        modelingBox = wx.StaticBox(self, wx.ID_ANY, "Modeling")

        self.infoBar = wx.InfoBar(self)
        # config file
        self.configFileCtrl = filebrowse.FileBrowseButton(self, labelText='Configuration:', changeCallback=self._loadConfiguration)
        self.configFileCtrl.SetValue(self.configFile, 0)
        # events
        self.eventsCtrl = wx.Choice(dashBox, choices=[])
        self.recordCtrl = wx.Choice(dashBox, choices=[])
        self.deleteAttempt = wx.Button(dashBox, label="Delete")
        self.eventsCtrl.Bind(wx.EVT_CHOICE, self._onEventChanged)
        self.deleteAttempt.Bind(wx.EVT_BUTTON, lambda evt: self.DeleteAttempt())

        baselineButton = wx.Button(modelingBox, label="Compute baseline")
        # treatment area
        self.treatmentSelect = Select(modelingBox, size=(-1, -1), type='region')
        defaultRegion = wx.Button(modelingBox, label="Default")
        startTreatmentButton = wx.Button(self, label="Start")
        stopTreatmentButton = wx.Button(self, label="Stop")

        runBtn = wx.Button(modelingBox, label="Run simulation")
        visualizationBtn = wx.Button(modelingBox, label="Switch visualization")

        runBtn.Bind(wx.EVT_BUTTON, lambda evt: self.RunSimulation())
        visualizationBtn.Bind(wx.EVT_BUTTON, lambda evt: self.ShowResults())
        baselineButton.Bind(wx.EVT_BUTTON, lambda evt: self.ComputeBaseline())
        startTreatmentButton.Bind(wx.EVT_BUTTON, lambda evt: self.StartTreatment())
        stopTreatmentButton.Bind(wx.EVT_BUTTON, lambda evt: self.StopTreatment())
        self.treatmentSelect.Bind(wx.EVT_TEXT, lambda evt: self.ChangeRegion())
        defaultRegion.Bind(wx.EVT_BUTTON, self._onDefaultRegion)

        self.Bind(wx.EVT_TIMER, self._displayResult, self.timer)
        self.Bind(EVT_PROCESS_NEW_EVENT, self._processForDashboard)
        self.Bind(EVT_PROCESS_BASELINE_NEW_EVENT, self._processBaseline)

        self.mainSizer = wx.BoxSizer(wx.VERTICAL)
        self.mainSizer.Add(self.infoBar, flag=wx.EXPAND)
        sizer = wx.BoxSizer(wx.HORIZONTAL)
        sizer.Add(self.configFileCtrl, proportion=1, flag=wx.ALIGN_CENTER_VERTICAL, border=5)
        self.mainSizer.Add(sizer, flag=wx.EXPAND | wx.ALL, border=5)
        sizer = wx.BoxSizer(wx.HORIZONTAL)
        sizer.Add(startTreatmentButton, proportion=1, flag=wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, border=5)
        sizer.Add(stopTreatmentButton, proportion=1, flag=wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, border=5)
        self.mainSizer.Add(sizer, flag=wx.EXPAND | wx.ALL, border=5)

        boxSizer = wx.StaticBoxSizer(dashBox, wx.HORIZONTAL)
        sizer = wx.BoxSizer(wx.HORIZONTAL)
        sizer.Add(wx.StaticText(dashBox, label="Events:"), flag=wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, border=5)
        sizer.Add(self.eventsCtrl, proportion=1, flag=wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, border=5)
        sizer.Add(self.recordCtrl, proportion=1, flag=wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, border=5)
        sizer.Add(self.deleteAttempt, proportion=0, flag=wx.ALIGN_CENTER_VERTICAL, border=5)
        boxSizer.Add(sizer, proportion=1, flag=wx.EXPAND | wx.ALL, border=5)
        self.mainSizer.Add(boxSizer, flag=wx.EXPAND | wx.ALL, border=5)

        boxSizer = wx.StaticBoxSizer(modelingBox, wx.VERTICAL)
        if self.configuration and 'scenarios' in self.configuration['POPS']:
            sizer = wx.BoxSizer(wx.HORIZONTAL)
            sizer.Add(wx.StaticText(modelingBox, label="Scenarios:"), flag=wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, border=10)
            for scen in self.configuration['POPS']['scenarios']:
                choices = self.configuration['POPS']['scenarios'][scen]['options']
                self.scenarios[scen] = wx.Choice(modelingBox, choices=choices)
                self.scenarios[scen].SetSelection(0)
                sizer.Add(wx.StaticText(modelingBox, label=scen.title() + ':'), flag=wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, border=5)
                sizer.Add(self.scenarios[scen], proportion=1, flag=wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, border=5)
            boxSizer.Add(sizer, flag=wx.EXPAND | wx.ALL, border=5)

        sizer = wx.BoxSizer(wx.HORIZONTAL)
        sizer.Add(runBtn, proportion=1, flag=wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, border=5)
        sizer.Add(visualizationBtn, proportion=1, flag=wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, border=5)
        sizer.Add(baselineButton, proportion=1, flag=wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, border=5)
        boxSizer.Add(sizer, flag=wx.EXPAND | wx.ALL, border=5)

        sizer = wx.BoxSizer(wx.HORIZONTAL)
        sizer.Add(wx.StaticText(modelingBox, label="Treatment area:"), flag=wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, border=5)
        sizer.Add(self.treatmentSelect, proportion=1, flag=wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, border=5)
        sizer.Add(defaultRegion, proportion=0, flag=wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, border=5)
        boxSizer.Add(sizer, flag=wx.EXPAND | wx.ALL, border=5)

        self.mainSizer.Add(boxSizer, flag=wx.EXPAND | wx.ALL, border=5)

        self.SetSizer(self.mainSizer)
        self.mainSizer.Fit(self)

        self._bindButtons()

        self.Bind(EVT_UPDATE_DISPLAY, self.OnDisplayUpdate)
        self.Bind(EVT_UPDATE_TIME_DISPLAY, self.OnTimeDisplayUpdate)

    def _connect(self):
        self._connectDashboard()
        self._connectSteering()
        if self.dashboard:
            self._loadBaseline()
            self._loadCharts()
        self._bindButtons()

    def _connectSteering(self):
        if self.socket:
            return
        urlS = self.configuration['POPS']['urlSteering']
        if not urlS:
            return
        urlS = urlS.replace('http://', '')
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
        self.dashboard = DashBoardRequests()
        urlD = self.configuration['POPS']['urlDashboard']
        if urlD:
            if not urlD.startswith('http'):
                urlD = 'http://' + urlD
            self.dashboard.set_root_URL(urlD)
            self.eventsByIds = dict(zip(*self.dashboard.get_events()))
            self.eventsByName = dict(reversed(item) for item in self.eventsByIds.items())
            self.eventsCtrl.SetItems(self.eventsByIds.values())

            if self.eventsByIds:
                self.eventsCtrl.SetStringSelection(self.eventsByIds[sorted(self.eventsByIds.keys())[-1]])
                self.playersByIds = dict(zip(*self.dashboard.get_players(self.eventsByName[self.eventsCtrl.GetStringSelection()])))
                self.playersByName = dict(reversed(item) for item in self.playersByIds.items())
            else:
                self.dashboard = None
                wx.MessageBox(message="No event in dashboard", style=wx.ICON_WARNING)
        else:
            self.dashboard = None

    def _onEventChanged(self, event):
        selectedEventName = self.eventsCtrl.GetStringSelection()
        self.playersByIds = dict(zip(*self.dashboard.get_players(self.eventsByName[selectedEventName])))
        self.playersByName = dict(reversed(item) for item in self.playersByIds.items())

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
        try:
            selectedPlayer, attempt = self.recordCtrl.GetStringSelection().split(':')
            if self.bar:
                self.bar.removeAttempt(selectedPlayer, int(attempt))
                jsonfile = os.path.join(self.configuration['logDir'], 'bar_{e}.json'.format(e=event))
                self.dashboard.post_data_bar(jsonfile=jsonfile, eventId=self.eventsByName[event])
            if self.radar:
                self.radar[selectedPlayer].removeAttempt(int(attempt))
                jsonfile = os.path.join(self.configuration['logDir'], 'radar_{p}_{e}.json'.format(p=selectedPlayer, e=event))
                self.dashboard.post_data_radar(jsonfile, self.eventsByName[event], self.playersByName[selectedPlayer])

            self.recordCtrl.Delete(self.recordCtrl.GetSelection())
            cnt = self.recordCtrl.GetCount()
            if cnt > 0:
                self.recordCtrl.SetSelection(self.recordCtrl.GetCount() - 1)
        except AttributeError:
            pass

    def _loadConfiguration(self, event):
        self.configFile = self.configFileCtrl.GetValue().strip()
        if self.configFile:
            self.settings['POPS']['config'] = self.configFile
            with open(self.configFile, 'r') as f:
                self.configuration = json.load(f)
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
                    name = os.path.basename(path).replace('.pack', '')
                    # avoid showing aggregate result
                    # player_attempt_event_year_month_day
                    if re.search('[0-9]*_[0-9]*_[0-9]*$', name):
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
        if self.dashboard:
            event = self.eventsCtrl.GetStringSelection()
            name, attempt = self.recordCtrl.GetStringSelection().split(':')
        else:
            event = 'tmpevent'
            attempt = '1'
            name = self._createPlayerName()
        self.AddLayersAsAnimation(etype='raster', pattern="{n}_{a}_{e}_*".format(n=name, e=event, a=attempt))

    def ShowProbability(self, event=None):
        if self.dashboard:
            event = self.eventsCtrl.GetStringSelection()
            name, attempt = self.recordCtrl.GetStringSelection().split(':')
        else:
            event = 'tmpevent'
            attempt = '1'
            name = self._createPlayerName()
        name = self.configuration['POPS']['model']['probability'] + '_' + name + '_' + attempt + '_' + event

        gscript.run_command('r.colors', map=name, quiet=True,
                            rules=self.configuration['POPS']['color_probability'])
        cmd = ['d.rast', 'values=0-10', 'flags=i', 'map={}'.format(name)]
        self.RemoveAllResultsLayers()
        self.ShowTreatment()
        ll = self.giface.GetLayerList()
        ll.AddLayer('raster', name=name, checked=True, opacity=1, cmd=cmd)

    def ShowTreatment(self, event=None):
        if self.dashboard:
            event = self.eventsCtrl.GetStringSelection()
            name, attempt = self.recordCtrl.GetStringSelection().split(':')
        else:
            event = 'tmpevent'
            attempt = '1'
            name = self._createPlayerName()
        name = self.configuration['POPS']['treatments'] + '_' + name + '_' + attempt + '_' + event

        env = get_environment(raster=name)
        gscript.run_command('r.to.vect', flags='st', input=name, output=name, type='area', env=env)
        gscript.run_command('v.generalize', input=name, output=name + '_gen', method='snakes', threshold=10, env=env)
        # test if vector exists (if any treatment was done)
        if gscript.find_file(name=name + '_gen', element='vector')['fullname']:
            cmd = ['d.vect', 'map={}'.format(name + '_gen'), 'color=none', 'fill_color=144:238:144']
            ll = self.giface.GetLayerList()
            ll.AddLayer('vector', name=name + '_gen', checked=True, opacity=1, cmd=cmd)

    def _createPlayerName(self):
        playerName = []
        for scen in self.scenarios:
            option = self.scenarios[scen].GetStringSelection()
            playerName.append(self.configuration['POPS']['scenarios'][scen]['alias'])
            playerName.append(option)
        return '_'.join(playerName)

    def _RunSimulation(self, event=None):
        print '_runSimulation'
        if self.switchCurrentResult == 0:
            # it's allowed to interact now
            # just to be sure remove results
            self.RemoveAllResultsLayers()
            wx.FutureCall(self.configuration['POPS']['waitBeforeRun'], self.RunSimulation)

    def RunSimulation(self, event=None):
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

        playerName = self._createPlayerName()
        if self.dashboard:
            eventId = self.eventsByName[self.eventsCtrl.GetStringSelection()]
            pid, _ = self.dashboard.create_player(playerName, eventId)
            if not pid:
                return
            self.playersByIds[pid] = playerName
            self.playersByName[playerName] = pid

            attempts = []
            if self.bar:
                attempts = self.bar.getAllAttempts(playerName)
            if not attempts:
                attempts = [1]
                new_attempt = '1'
            else:
                new_attempt = str(max(attempts) + 1)

            attempt = "{p}:{a}".format(p=playerName, a=new_attempt)
            self.recordCtrl.Append(attempt)
            self.recordCtrl.SetStringSelection(attempt)

        # update for scenarios:
        for scen in self.scenarios:
            option = self.scenarios[scen].GetStringSelection()
            params = self.configuration['POPS']['scenarios'][scen]['values'].keys()
            for param in params:
                if param in self.configuration['POPS']:
                    value = self.configuration['POPS']['scenarios'][scen]['values'][param][option]
                    self.configuration['POPS'][param] = value

        # grab a new raster of conditions
        # process new input layer
        treatments = self.configuration['POPS']['treatments']
        treatments_resampled = treatments + '_resampled'
        studyArea = self.configuration['tasks'][self.current]['base']
        species = self.configuration['POPS']['model']['species']
        infected = self.configuration['POPS']['model']['infected']
        species_treated = self.configuration['POPS']['species_treated']
        all_trees = self.configuration['POPS']['model']['lvtree']
        all_trees_treated = self.configuration['POPS']['all_trees_treated']
        inf_treated = self.configuration['POPS']['infected_treated']
        probability = self.configuration['POPS']['model']['probability']
        treatment_efficacy = self.configuration['POPS']['treatment_efficacy']
        price_function = self.configuration['POPS']['price']

        env = get_environment(raster=studyArea, align=species)

        self.treated_area = self.computeTreatmentArea(treatments)
        price_per_m2 = eval(price_function.format(treatment_efficacy))
        self.money_spent = self.treated_area * price_per_m2

        # compute proportion
        if gscript.raster_info(treatments)['ewres'] < gscript.raster_info(species)['ewres']:
            gscript.run_command('r.resamp.stats', input=treatments, output=treatments_resampled, flags='w', method='count', env=env)
            maxvalue = gscript.raster_info(treatments_resampled)['max']
            gscript.mapcalc("{p} = if(isnull({t}), 0, {t} / {m})".format(p=treatments_resampled + '_proportion', t=treatments_resampled, m=maxvalue), env=env)
            gscript.run_command('g.rename', raster=[treatments_resampled + '_proportion', treatments_resampled], env=env)
        else:
            gscript.run_command('r.resamp.stats', input=treatments, output=treatments_resampled, flags='w', method='average', env=env)
            gscript.run_command('r.null', map=treatments_resampled, null=0, env=env)

        if self.treated_area:
            gscript.mapcalc("{s} = int({l} - {l} * {t} * {e})".format(s=species_treated, t=treatments_resampled,
                                                                   i=infected, l=species, e=treatment_efficacy), env=env)
        else:  # when there is no treatment
            gscript.mapcalc("{s} = int(if ({i} == 0, {l}, max(1, {l})))".format(s=species_treated, i=infected, l=species), env=env)

        # TODO: revisit this
        gscript.mapcalc("{ni} = min({i}, {st})".format(i=infected, st=species_treated, ni=inf_treated), env=env)
        # this is not used in pops
        gscript.mapcalc("{att} = round({at} - ({s} - {st}))".format(at=all_trees, att=all_trees_treated, st=species_treated, s=species), env=env)

#        gscript.mapcalc("{att} = if(isnull({tr}), {at}, if ({at} - ({sp} - {st}) < 0, 1, {at} - ({sp} - {st})))".format(tr=treatments,
#                        at=all_trees, att=all_trees_treated, st=species_treated, sp=species), env=env)

        if self.dashboard:
            postfix = playerName + '_' + new_attempt + '_' + self.eventsByIds[eventId]
        else:
            postfix = playerName + '_' + '1' + '_' + 'tmpevent'
        probability = probability + '_' + postfix
        # todo, save treatments
        gscript.run_command('g.copy', raster=[treatments, treatments + '_' + postfix], env=env)
        self.lastRecordedTreatment = treatments + '_' + postfix
        extent = gscript.raster_info(studyArea)
        region = '{n},{s},{w},{e},{a}'.format(n=extent['north'], s=extent['south'],
                                              w=extent['west'], e=extent['east'], a=species)

        model_params = self.configuration['POPS']['model'].copy()
        model_params.update({'output': postfix, 'output_series': postfix,
                             'probability': probability, 'species': species_treated})
        # update for scenarios:
        for scen in self.scenarios:
            option = self.scenarios[scen].GetStringSelection()
            params = self.configuration['POPS']['scenarios'][scen]['values'].keys()
            for param in params:
                if param in model_params:
                    value = self.configuration['POPS']['scenarios'][scen]['values'][param][option]
                    model_params.update({param: value})
        # run simulation
        message = 'cmd:start:'
        message += "region=" + region
        for key in model_params:
            message += '|'
            message += '{k}={v}'.format(k=key, v=model_params[key])

        self.RemoveAllResultsLayers()

        self.socket.sendall(message)

    def computeTreatmentArea(self, treatments):
        env = get_environment(raster=treatments)
        univar = gscript.parse_command('r.univar', flags='g', map=treatments, env=env)
        if not univar or float(univar['sum']) == 0:
            return 0
        else:
            res = gscript.region(env=env)
            return float(univar['n']) * res['nsres'] * res['ewres']

    def _run(self):
        self.socket.sendall('cmd:play')

    def _stop(self):
        self.socket.sendall('cmd:end')

    def _displayResult(self, event):
        if not self.resultsToDisplay.empty():
            name = self.resultsToDisplay.get()
            gscript.run_command('r.colors', map=name, quiet=True,
                                rules=self.configuration['POPS']['color_trees'])
            cmd = ['d.rast', 'values=0', 'flags=i', 'map={}'.format(name)]
            evt = addLayers(layerSpecs=[dict(ltype='raster', name=name, cmd=cmd, checked=True), ])
            # uncheck previous one (lethal temperature can remove infection)
            if self.lastDisplayedLayerAnim:
                ll = self.giface.GetLayerList()
                found = ll.GetLayersByName(self.lastDisplayedLayerAnim)
                if found:
                    evtCheck = checkLayers(layers=found, checked=False)
                    self.scaniface.postEvent(self.scaniface, evtCheck)
            self.lastDisplayedLayerAnim = name
            self.scaniface.postEvent(self.scaniface, evt)
            # update year
            res = re.search("_20[0-9]{2}_", name)
            if res:
                year = res.group().strip('_')
                evt2 = updateTimeDisplay(value=year)
                self.scaniface.postEvent(self, evt2)

    def ComputeBaseline(self):
        self.infoBar.ShowMessage("Computing baseline...")
        studyArea = self.configuration['tasks'][self.current]['base']
        extent = gscript.raster_info(studyArea)
        species = self.configuration['POPS']['model']['species']
        region = '{n},{s},{w},{e},{a}'.format(n=extent['north'], s=extent['south'],
                                              w=extent['west'], e=extent['east'], a=species)
        message = 'cmd:baseline:'
        message += 'region=' + region
        baseline_model = self.configuration['POPS']['model'].copy()
        baseline_model.update(self.configuration['POPS']['baseline'])
        for key in baseline_model:
            message += '|'
            message += '{k}={v}'.format(k=key, v=baseline_model[key])

        self.socket.sendall(message)

    def _loadBaseline(self):
        # load baseline from dashboard when starting
        self.baselineValues = []
        self.baselineScaledValues = []
        json = self.dashboard.get_baseline_barJson()
        if json:
            path = os.path.join(self.configuration['logDir'], 'barBaseline.json')
            self.barBaseline = BarData(filePath=path, columns=self.configuration['POPS']['dashboard']['columns'])
            self.barBaseline.setDataFromJson(json)
            self.baselineValues = self.barBaseline.getBaseline()
        json = self.dashboard.get_baseline_radarJson()
        if json:
            path = os.path.join(self.configuration['logDir'], 'radarBaseline.json')
            self.radarBaseline = RadarData(filePath=path, columns=self.configuration['POPS']['dashboard']['columns'])
            self.radarBaseline.setDataFromJson(json)
            self.baselineScaledValues = self.radarBaseline.getBaselineScaledValues()

    def _loadCharts(self):
        # load charts from dashboard when starting
        eventId = self.eventsByName[self.eventsCtrl.GetStringSelection()]
        eventName = self.eventsByIds[eventId]
        json = self.dashboard.get_data_barJson(eventId)
        if json:
            path = os.path.join(self.configuration['logDir'], 'bar_{e}.json'.format(e=eventName))
            self.bar = BarData(filePath=path, columns=self.configuration['POPS']['dashboard']['columns'])
            self.bar.setDataFromJson(json)

            # recreate records:
            records = []
            playerIds, playerNames = self.dashboard.get_players(eventId)
            for playerName in playerNames:
                attempts = self.bar.getAllAttempts(playerName)
                for a in attempts:
                    records.append(playerName + ':' + str(a))
            self.recordCtrl.SetItems(records)

        playerIds, playerNames = self.dashboard.get_players(eventId)
        for playerId, playerName in zip(playerIds, playerNames):
            json = self.dashboard.get_data_radarJson(eventId, playerId)
            if json:
                path = os.path.join(self.configuration['logDir'], 'radar_{p}_{e}.json'.format(p=playerName, e=eventName))
                self.radar[playerName] = RadarData(filePath=path, columns=self.configuration['POPS']['dashboard']['columns'])
                self.radar[playerName].setDataFromJson(json)
        return True

    def _reloadAnalysisFile(self, funcPrefix):
        analysesFile = os.path.join(self.configuration['taskDir'], self.configuration['tasks'][self.current]['analyses'])
        try:
            myanalyses = imp.load_source('myanalyses', analysesFile)
        except StandardError:
            return None
        functions = [func for func in dir(myanalyses) if func.startswith(funcPrefix)]
        for func in functions:
            exec('del myanalyses.' + func)
        try:
            myanalyses = imp.load_source('myanalyses', analysesFile)
        except StandardError:
            return None
        functions = [func for func in dir(myanalyses) if func.startswith(funcPrefix)]
        return myanalyses, functions

    def _processBaseline(self, event):
        self.infoBar.ShowMessage("Processing baseline...")

        # run analyses for dashboard
        myanalyses, functions = self._reloadAnalysisFile(funcPrefix='pops')
        for func in functions:
            try:
                exec('self.baselineValues, baselineRadar = myanalyses.' + func + "(infected=event.result,"
                                                " money_spent=0,"
                                                " treated_area=0,"
                                                " baselineValues=[],"
                                                " pops=self.configuration['POPS'],"
                                                " baseline=True)")
            except (CalledModuleError, StandardError, ScriptError):
                print traceback.print_exc()

        if self.dashboard:
            path = os.path.join(self.configuration['logDir'], 'radarBaseline.json')
            self.radarBaseline = RadarData(filePath=path, baseline=self.baselineValues,
                                           columns=self.configuration['POPS']['dashboard']['columns'])
            self.dashboard.post_baseline_radar(path)
            path = os.path.join(self.configuration['logDir'], 'barBaseline.json')
            self.barBaseline = BarData(filePath=path, baseline=self.baselineValues, columns=self.configuration['POPS']['dashboard']['columns'])
            self.dashboard.post_baseline_bar(path)

        self.infoBar.Dismiss()

    def _processForDashboard(self, event):
        # run analyses for dashboard
        myanalyses, functions = self._reloadAnalysisFile(funcPrefix='pops')
        for func in functions:
            try:
                exec('resultsBar, resultsRadar = myanalyses.' + func + "(infected=event.result,"
                                                " money_spent=self.money_spent,"
                                                " treated_area=self.treated_area,"
                                                " baselineValues=self.baselineValues,"
                                                " pops=self.configuration['POPS'],"
                                                " baseline=False)")
            except (CalledModuleError, StandardError, ScriptError):
                print traceback.print_exc()

        if self.dashboard:
            playerName = self.recordCtrl.GetStringSelection().split(':')[0]
            playerId = self.playersByName[playerName]
            eventName = self.eventsCtrl.GetStringSelection()

            path = os.path.join(self.configuration['logDir'], 'radar_{p}_{e}.json'.format(p=playerName, e=eventName))
            if playerName not in self.radar:
                self.radar[playerName] = RadarData(filePath=path, baseline=self.baselineValues,
                                                   columns=self.configuration['POPS']['dashboard']['columns'])
            self.radar[playerName].addRecord(resultsRadar, resultsBar, baseline=False)
            eventId = self.eventsByName[self.eventsCtrl.GetStringSelection()]
            self.dashboard.post_data_radar(jsonfile=path, eventId=eventId, playerId=playerId)

    #        record = (infected_cells * res * res, money, treated, crop_affected_area)
            path = os.path.join(self.configuration['logDir'], 'bar_{e}.json'.format(e=eventName))  # maybe named with event
            if not self.bar:
                self.bar = BarData(filePath=path, baseline=self.baselineValues, columns=self.configuration['POPS']['dashboard']['columns'])
            self.bar.addRecord(resultsBar, playerName)
            self.dashboard.post_data_bar(jsonfile=path, eventId=eventId)

        self.infoBar.Dismiss()
        self._currentlyRunning = False
        self.switchCurrentResult = 1

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
        if self.timer.IsRunning():
            return
        self._connect()
        self._loadConfiguration(None)
        self.showDisplayChange = True
        self.switchCurrentResult = 0
        self.scaniface.additionalParams4Analyses = {"pops": self.configuration['POPS']}
        self.LoadLayers()
        if self.treatmentSelect.GetValue():
            self.ChangeRegion()

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

    def ChangeRegion(self):
        region = self.treatmentSelect.GetValue()
        # if empty, go back to default
        if not region:
            # set for scanning treatments
            self.settings['scan']['elevation'] = self.configuration['tasks'][self.current]['base']
            self.settings['scan']['region'] = ''
            self.ZoomToBase()
            self.scaniface.changedInput = True
        else:
            # check if exists
            region = region.split('@')[0]
            f = gscript.find_file(name=region, element='windows')
            if not f['fullname']:
                return

            # set for scanning treatments
            self.settings['scan']['elevation'] = ''
            self.settings['scan']['region'] = region
            self.ZoomToRegion(region)
            self.scaniface.changedInput = True

    def _onDefaultRegion(self, event):
        self.treatmentSelect.SetValue('')

    def LoadLayers(self):
        ll = self.giface.GetLayerList()
        for i, cmd in enumerate(self.configuration['tasks'][self.current]['layers']):
            opacity = 1.0
            checked = True
            if "layers_opacity" in self.configuration['tasks'][self.current]:
                opacity = float(self.configuration['tasks'][self.current]['layers_opacity'][i])
            if "layers_checked" in self.configuration['tasks'][self.current]:
                checked = float(self.configuration['tasks'][self.current]['layers_checked'][i])
            if cmd[0] == 'd.rast':
                l = ll.AddLayer('raster', name=cmd[1].split('=')[1], checked=checked,
                                opacity=opacity, cmd=cmd)
            elif cmd[0] == 'd.vect':
                l = ll.AddLayer('vector', name=cmd[1].split('=')[1], checked=checked,
                                opacity=opacity, cmd=cmd)
            elif cmd[0] == 'd.labels':
                l = ll.AddLayer('labels', name=cmd[1].split('=')[1], checked=checked,
                                opacity=opacity, cmd=cmd)
            elif cmd[0] == 'd.shade':
                l = ll.AddLayer('shaded', name=cmd[1].split('=')[1], checked=checked,
                                opacity=opacity, cmd=cmd)
            elif cmd[0] == 'd.rgb':
                l = ll.AddLayer('rgb', name=cmd[1].split('=')[1], checked=checked,
                                opacity=opacity, cmd=cmd)
            elif cmd[0] == 'd.legend':
                l = ll.AddLayer('rastleg', name=cmd[1].split('=')[1], checked=checked,
                                opacity=opacity, cmd=cmd)
            elif cmd[0] == 'd.northarrow':
                l = ll.AddLayer('northarrow', name=cmd[1].split('=')[1], checked=checked,
                                opacity=opacity, cmd=cmd)
            else:
                l = ll.AddLayer('command', name=' '.join(cmd), checked=checked,
                                opacity=opacity, cmd=[])
            if not checked:
                # workaround: in not checked the order of layers is wrong
                try:
                    for each in ll:
                        ll.SelectLayer(each, False)
                    ll.SelectLayer(l, True)
                except AttributeError:
                    # SelectLayer introduced in r73097, for cases before:
                    ll._tree.Unselect()
                    ll._tree.SelectItem(l._layer, True)

        # zoom to base map
        self.ZoomToBase()

    def ZoomToBase(self):
        base = self.configuration['tasks'][self.current]['base']
        self.giface.GetMapWindow().Map.GetRegion(rast=[base], update=True)
        self.giface.GetMapWindow().UpdateMap()

    def ZoomToRegion(self, region):
        self.giface.GetMapWindow().Map.GetRegion(regionName=region, update=True)
        self.giface.GetMapWindow().UpdateMap()

    def RemoveAllResultsLayers(self):
        event = self.eventsCtrl.GetStringSelection()
        pattern_layers_r = gscript.list_grouped(type='raster', pattern="*{}*".format(event))[gscript.gisenv()['MAPSET']]
        pattern_layers_v = gscript.list_grouped(type='vector', pattern="*{}*".format(event))[gscript.gisenv()['MAPSET']]
        self.RemoveLayers(layers=pattern_layers_r + pattern_layers_v)

    def RemoveLayers(self, etype='raster', pattern=None, layers=None):
        # works only for raster/vector at this point
        all_layers = []
        if pattern:
            pattern_layers = gscript.list_grouped(type=etype, pattern=pattern)[gscript.gisenv()['MAPSET']]
            all_layers += pattern_layers
        if layers:
            all_layers += layers
        ll = self.giface.GetLayerList()
        for l in reversed(ll):
            if l.maplayer.name:
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
        self.lastDisplayedLayerAnim = ''
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
