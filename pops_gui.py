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

from activities_dashboard import DashboardFrame, MultipleDashboardFrame


ProcessForDashboardEvent, EVT_PROCESS_NEW_EVENT = wx.lib.newevent.NewEvent()
updateDisplay, EVT_UPDATE_DISPLAY = wx.lib.newevent.NewEvent()
updateTimeDisplay, EVT_UPDATE_TIME_DISPLAY = wx.lib.newevent.NewEvent()
updateInfoBar, EVT_UPDATE_INFOBAR = wx.lib.newevent.NewEvent()

TMP_DIR = '/tmp/test_SOD/'
try:
    os.mkdir(TMP_DIR)
except OSError:
    pass


### naming scheme for outputs: ###
# event__scenario/player__mainAttempt_subAttmpt__year_month_day
# probability__event__scenario/player__mainAttempt_subAttmpt__year_month_day


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

        # steering
        self.visualizationModes = ['singlerun', 'probability']
        self.visualizationMode = 0
        self.currentCheckpoint = None
        self.checkpoints = []
        self.attempt = Attempt()
        self._threadingEvent = threading.Event()
        self.model_running = False

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

        modelingBox = wx.StaticBox(self, wx.ID_ANY, "Modeling")

        self.infoBar = wx.InfoBar(self)
        # config file
        self.configFileCtrl = filebrowse.FileBrowseButton(self, labelText='Configuration:', changeCallback=self._loadConfiguration)
        self.configFileCtrl.SetValue(self.configFile, 0)

        # treatment area
        self.treatmentSelect = Select(modelingBox, size=(-1, -1), type='region')
        defaultRegion = wx.Button(modelingBox, label="Default")
        startTreatmentButton = wx.Button(self, label="Start")
        stopTreatmentButton = wx.Button(self, label="Stop")

        runBtn = wx.Button(modelingBox, label="Run simulation")
        visualizationBtn = wx.Button(modelingBox, label="Switch visualization")

        runBtn.Bind(wx.EVT_BUTTON, lambda evt: self.RunSimulation())
        visualizationBtn.Bind(wx.EVT_BUTTON, lambda evt: self.SwitchVizMode())
        startTreatmentButton.Bind(wx.EVT_BUTTON, lambda evt: self.StartTreatment())
        stopTreatmentButton.Bind(wx.EVT_BUTTON, lambda evt: self.StopTreatment())
        self.treatmentSelect.Bind(wx.EVT_TEXT, lambda evt: self.ChangeRegion())
        defaultRegion.Bind(wx.EVT_BUTTON, self._onDefaultRegion)

        self.Bind(wx.EVT_TIMER, self._displayResult, self.timer)

        self.mainSizer = wx.BoxSizer(wx.VERTICAL)
        self.mainSizer.Add(self.infoBar, flag=wx.EXPAND)
        sizer = wx.BoxSizer(wx.HORIZONTAL)
        sizer.Add(self.configFileCtrl, proportion=1, flag=wx.ALIGN_CENTER_VERTICAL, border=5)
        self.mainSizer.Add(sizer, flag=wx.EXPAND | wx.ALL, border=5)
        sizer = wx.BoxSizer(wx.HORIZONTAL)
        sizer.Add(startTreatmentButton, proportion=1, flag=wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, border=5)
        sizer.Add(stopTreatmentButton, proportion=1, flag=wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, border=5)
        self.mainSizer.Add(sizer, flag=wx.EXPAND | wx.ALL, border=5)

        boxSizer = wx.StaticBoxSizer(modelingBox, wx.VERTICAL)
        sizer = wx.BoxSizer(wx.HORIZONTAL)
        sizer.Add(runBtn, proportion=1, flag=wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, border=5)
        sizer.Add(visualizationBtn, proportion=1, flag=wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, border=5)
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
        self.Bind(EVT_UPDATE_INFOBAR, self.OnUpdateInfoBar)

    def _connect(self):
        self._connectSteering()
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
        self.clientthread = threading.Thread(target=self._client, args=(self.resultsToDisplay, self._threadingEvent))
        self.clientthread.start()

    def OnDisplayUpdate(self, event):
        if not self.dashboardFrame:
            return
        if self.showDisplayChange:
            self.dashboardFrame.show_value(event.value)

    def OnTimeDisplayUpdate(self, event):
        if not self.timeDisplay:
            return
        self.timeDisplay.Update(*event.date)

    def OnUpdateInfoBar(self, event):
        if event.dismiss:
            self.infoBar.Dismiss()
        if event.message:
            self.infoBar.ShowMessage(event.message)

    def _loadConfiguration(self, event):
        self.configFile = self.configFileCtrl.GetValue().strip()
        if self.configFile:
            self.settings['POPS']['config'] = self.configFile
            with open(self.configFile, 'r') as f:
                self.configuration = json.load(f)
        else:
            self.settings['activities']['config'] = ''

    def _debug(self, msg):
        with open('/tmp/debug.txt', 'a+') as f:
            f.write(':'.join(msg))
            f.write('\n')

    def _client(self, resultsToDisplay, event):
        while self.isRunningClientThread:
            data = self.socket.recv(1024)
            if not data:
                # GUI received close from server
                # finish while loop
                self.socket.close()
                continue
            self._debug(msg=['starts'])
            message = data.split(':')
            if message[0] == 'clientfile':
                self._debug(message)
                _, fsize, path = message
                with open(message[2], 'rb') as f:
                    data = f.read()
                    try:
                        self.socket.sendall(data)
                    except socket.error:
                        print 'erroro sending file'
            elif message[0] == 'serverfile':
                self._debug(message)
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
                    # event_player_year_month_day
                    if re.search('[0-9]*_[0-9]*_[0-9]*$', name):
                        print name
                        resultsToDisplay.put(name)
                        print 'display'

                ##########
            elif message[0] == 'info':
                self._debug(message)
                if message[1] == 'last':
                    name = message[2]
#                    evt = ProcessForDashboardEvent(result=name)
                    evt = updateInfoBar(dismiss=True, message=None)
                    wx.PostEvent(self, evt)
                    # rename layers to save unique scenario
                    self._renameAllAfterSimulation(name)
                elif message[1] == 'received':
                    print "event.set()"
                    event.set()
                elif message[1] == 'model_running':
                    self.model_running = True if message[2] == 'yes' else False
                    event.set()

    def _renameAllAfterSimulation(self, name):
        event, player, date = name.split('__')
        a1, a2 = self.attempt.getCurrent()
        pattern = "{e}__{n}__[0-9]{{4}}_[0-9]{{2}}_[0-9]{{2}}".format(n=player, e=event)
        pattern_layers = gscript.list_grouped(type='raster', pattern=pattern, flag='e')[gscript.gisenv()['MAPSET']]
        if pattern_layers:
            for layer in pattern_layers:
                components = layer.split('__')
                new_name = '__'.join(components[:-1] + ['{a1}_{a2}'.format(a1=a1, a2=a2)] + components[-1:])
                gscript.run_command('g.copy', raster=[layer, new_name], quiet=True, overwrite=True)
#
#    def ShowResults(self, event=None):
#        # clear the queue to stop animation
#        with self.resultsToDisplay.mutex:
#            self.resultsToDisplay.queue.clear()
#
#        if self.switchCurrentResult == 0:
#            self.visualizationMode = 'animation'
#            self.ShowAnimation()
#        elif self.switchCurrentResult == 1:
#            self.ShowProbability()
#            self.visualizationMode = 'probability'
#        elif self.switchCurrentResult == 2:
#            self.RemoveAllResultsLayers()
#            self.showDisplayChange = True
#            self.visualizationMode = 'singlerun'
#
#        self.switchCurrentResult += 1
#        if self.switchCurrentResult >= 3:
#            self.switchCurrentResult = 0

    def SwitchVizMode(self, event=None):
        # clear the queue to stop animation
        with self.resultsToDisplay.mutex:
            self.resultsToDisplay.queue.clear()

        self.visualizationMode += 1
        if self.visualizationMode >= len(self.visualizationModes):
            self.visualizationMode = 0
        self.ShowResults()

    def _createPlayerName(self):
        return 'player'

    def getEventName(self):
        return 'tmpevent'

    def ShowAnimation(self, event=None):
        event = self.getEventName()
        attempt = self.attempt.getCurrentFormatted(delim='_')
        name = self._createPlayerName()
        self.AddLayersAsAnimation(etype='raster', pattern="{e}__{n}__{a}_*".format(n=name, e=event, a=attempt))

#    def ShowProbability(self, event=None):
#        event = self.getEventName()
#        attempt = self.attempt.getCurrentFormatted(delim='_')
#        name = self._createPlayerName()
#        pattern = self.configuration['POPS']['model']['probability_series'] + '__' + event + '__' + name + '__' + attempt + '*'
#        pattern_layers = gscript.list_grouped(type='raster', pattern=pattern)[gscript.gisenv()['MAPSET']]
#
#        self.RemoveAllResultsLayers()
#        self.ShowTreatment(self.currentCheckpoint)
#        displayTime = self.checkpoints[self.currentCheckpoint]
#        for name in pattern_layers:
#            if "{y}_{m:02d}_{d:02d}".format(y=displayTime[0], m=displayTime[1], d=displayTime[2]) in name:
#                gscript.run_command('r.colors', map=name, quiet=True,
#                                    rules=self.configuration['POPS']['color_probability'])
#                cmd = ['d.rast', 'values=0-10', 'flags=i', 'map={}'.format(name)]
#                ll = self.giface.GetLayerList()
#                ll.AddLayer('raster', name=name, checked=True, opacity=1, cmd=cmd)

    def ShowResults(self):
        # change layers
        event = 'tmpevent'
        attempt = self.attempt.getCurrentFormatted(delim='_')
        name = self._createPlayerName()
        etype = 'raster'
        pattern = "{e}__{n}__{a}__*".format(n=name, e=event, a=attempt)

        if self.visualizationModes[self.visualizationMode] == 'singlerun':
            pattern_layers = gscript.list_grouped(type=etype, pattern=pattern)[gscript.gisenv()['MAPSET']]
        elif self.visualizationModes[self.visualizationMode] == 'probability':
            pattern = self.configuration['POPS']['model']['probability_series'] + '__' + pattern
            pattern_layers = gscript.list_grouped(type=etype, pattern=pattern)[gscript.gisenv()['MAPSET']]

        self.RemoveAllResultsLayers()
        self.ShowTreatment(self.currentCheckpoint)
        displayTime = self.checkpoints[self.currentCheckpoint]
        ll = self.giface.GetLayerList()
        for name in pattern_layers:
            if "{y}_{m:02d}_{d:02d}".format(y=displayTime[0], m=displayTime[1], d=displayTime[2]) in name:
                if self.visualizationModes[self.visualizationMode] == 'probability':
                    # TODO r.colors should be moved
                    gscript.run_command('r.colors', map=name, quiet=True, rules=self.configuration['POPS']['color_probability'])
                    cmd = ['d.rast', 'values=0', 'flags=i', 'map={}'.format(name)]
                elif self.visualizationModes[self.visualizationMode] == 'singlerun':
                    cmd = ['d.rast', 'values=0', 'flags=i', 'map={}'.format(name)]
                ll.AddLayer('raster', name=name, checked=True, opacity=1, cmd=cmd)

    def ShowTreatment(self, year):
        event = self.getEventName()
        attempt = str(self.attempt.getCurrent()[0])
        name = self._createPlayerName()
        name = '__'.join([self.configuration['POPS']['treatments'], event, name, attempt])
        cmd = ['d.vect', 'map={}'.format(name), 'display=shape,cat', 'fill_color=none', 'label_color=black', 'label_size=10', 'xref=center']
        ll = self.giface.GetLayerList()
        ll.AddLayer('vector', name=name, checked=True, opacity=1, cmd=cmd)

    def _RunSimulation(self, event=None):
        print '_runSimulation'
        if self.switchCurrentResult == 0:
            # it's allowed to interact now
            # just to be sure remove results
            self.RemoveAllResultsLayers()
            wx.FutureCall(self.configuration['POPS']['waitBeforeRun'], self.RunSimulation)

    def EndSimulation(self):
        if self._isModelRunning():
            self.socket.sendall('cmd:end')

    def InitSimulation(self):
        self._initSimulation(restart=False)
        self.attempt.increaseMajor()
        self.RemoveAllResultsLayers()

    def RestartSimulation(self):
        self._initSimulation(restart=True)
        self.attempt.increaseMajor()
        self.RemoveAllResultsLayers()
        
    def _initSimulation(self, restart):
        playerName = self._createPlayerName()

        # grab a new raster of conditions
        # process new input layer
        studyArea = self.configuration['tasks'][self.current]['base']
        host = self.configuration['POPS']['model']['host']
        probability = self.configuration['POPS']['model']['probability_series']

        postfix = 'tmpevent' + '__' + playerName + '_'
        probability = probability + '__' + postfix

        extent = gscript.raster_info(studyArea)
        region = '{n},{s},{w},{e},{a}'.format(n=extent['north'], s=extent['south'],
                                              w=extent['west'], e=extent['east'], a=host)

        model_params = self.configuration['POPS']['model'].copy()
        model_params.update({'output_series': postfix,
                             'probability_series': probability})
        # run simulation
        if restart:
            message = 'cmd:restart:'
        else:
            message = 'cmd:start:'
        message += "region=" + region
        for key in model_params:
            message += '|'
            message += '{k}={v}'.format(k=key, v=model_params[key])
        self.socket.sendall(message)

    def RunSimulation(self, event=None):
        if self._isModelRunning():
            # if simulation in the beginning, increase major version and restart the simulation
            if self.currentCheckpoint == 0:
                self.RestartSimulation()
            else:
                self.attempt.increaseMinor()
        else:
            self.InitSimulation()

        self.showDisplayChange = False
        # vis mode should be single run, not probability
        self.visualizationMode = 0

        self.infoBar.ShowMessage("Running...")
        playerName = self._createPlayerName()
        new_attempt = self.attempt.getCurrent()
        print new_attempt
        attempt = "{p}:{a1}.{a2}".format(p=playerName, a1=new_attempt[0], a2=new_attempt[1])

        # grab a new raster of conditions
        # process new input layer
        treatments = self.configuration['POPS']['treatments']
        treatments_resampled = treatments + '_resampled'
        studyArea = self.configuration['tasks'][self.current]['base']
        host = self.configuration['POPS']['model']['host']
        infected = self.configuration['POPS']['model']['infected']
        host_treated = self.configuration['POPS']['host_treated']
        all_trees = self.configuration['POPS']['model']['total_plants']
        all_trees_treated = self.configuration['POPS']['all_trees_treated']
        inf_treated = self.configuration['POPS']['infected_treated']
        probability = self.configuration['POPS']['model']['probability_series']
        treatment_efficacy = self.configuration['POPS']['treatment_efficacy']
        price_function = self.configuration['POPS']['price']

        env = get_environment(raster=studyArea, align=host)

        self.treated_area = self.computeTreatmentArea(treatments)
        price_per_m2 = eval(price_function.format(treatment_efficacy))
        self.money_spent = self.treated_area * price_per_m2

        event = 'tmpevent'
        postfix = 'tmpevent' + '__' + playerName + '_'
        probability = probability + '__' + postfix
        # todo, save treatments
        tr_name = '__'.join([treatments, event, playerName, "{a1}".format(a1=new_attempt[0]),
                             str(max(0, self.currentCheckpoint))])
        gscript.run_command('g.copy', raster=[treatments, tr_name], env=env)
        self.lastRecordedTreatment = treatments + '_' + postfix
        # create treatment vector of all used treatments in that scenario
        self.createTreatmentVector(tr_name, env)

        # compute proportion
        treatments_as_float = False
        if treatments_as_float:
            if gscript.raster_info(treatments)['ewres'] < gscript.raster_info(host)['ewres']:
                gscript.run_command('r.resamp.stats', input=treatments, output=treatments_resampled, flags='w', method='count', env=env)
                maxvalue = gscript.raster_info(treatments_resampled)['max']
                gscript.mapcalc("{p} = if(isnull({t}), 0, {t} / {m})".format(p=treatments_resampled + '_proportion', t=treatments_resampled, m=maxvalue), env=env)
                gscript.run_command('g.rename', raster=[treatments_resampled + '_proportion', treatments_resampled], env=env)
            else:
                gscript.run_command('r.resamp.stats', input=treatments, output=treatments_resampled, flags='w', method='average', env=env)
                gscript.run_command('r.null', map=treatments_resampled, null=0, env=env)
        else:
            gscript.run_command('r.null', map=treatments, null=0, env=env)

#        self.applyTreatments(host=host, host_treated=host_treated, efficacy=treatment_efficacy,
#                             treatment_prefix=treatments + '__' + postfix, env=env)
                                     

        gscript.mapcalc("{ni} = min({i}, {st})".format(i=infected, st=host_treated, ni=inf_treated), env=env)

        # export treatments file to server
        pack_path = os.path.join(TMP_DIR, treatments + '.pack')
        gscript.run_command('r.pack', input=treatments, output=pack_path, env=env)
        self.socket.sendall('clientfile:{}:{}'.format(os.path.getsize(pack_path), pack_path))
        self._threadingEvent.clear()
        self._threadingEvent.wait(2000)
        # load new data here
        tr_year = self.configuration['POPS']['model']['start_time'] + self.currentCheckpoint
        self.socket.sendall('load:' + str(tr_year) + ':' + treatments)
        self._threadingEvent.clear()
        self._threadingEvent.wait(2000)

        self.socket.sendall('cmd:goto:' + str(self.currentCheckpoint))
        self._threadingEvent.clear()
        self._threadingEvent.wait(2000)

        self.socket.sendall('cmd:sync')
        self._threadingEvent.clear()
        self._threadingEvent.wait(2000)

        self.socket.sendall('cmd:play')

        self.RemoveAllResultsLayers()

    def createTreatmentVector(self, lastTreatment, env):
        tr, evt, plr, attempt, year = lastTreatment.split('__')
        postfix = 'cat_year'
        gscript.write_command('r.reclass', input=lastTreatment, output=lastTreatment + '__' + postfix, rules='-',
                              stdin='1 = {y}'.format(y=int(year) + self.configuration['POPS']['model']['start_time']), env=env)
        pattern = '__'.join([tr, evt, plr, attempt, '*', postfix])
        layers = gscript.list_grouped(type='raster', pattern=pattern)[gscript.gisenv()['MAPSET']]
        to_patch = []
        for layer in layers:
            y = int(layer.split('__')[-2])
            if y <= int(year):
                to_patch.append(layer)
        name = '__'.join([tr, evt, plr, attempt])
        if len(to_patch) >= 2:
            to_patch = gscript.natural_sort(to_patch)[::-1]
            gscript.run_command('r.patch', input=to_patch, output=name, flags='z', env=env)
        else:
            gscript.run_command('g.copy', raster=[lastTreatment + '__' + postfix, name], env=env)
        gscript.run_command('r.to.vect', input=name, output=name + '_tmp', flags='vt', type='area', env=env)
        # for nicer look
        gscript.run_command('v.generalize', input=name + '_tmp', output=name, method='snakes', threshold=10, env=env)

    def computeTreatmentArea(self, treatments):
        env = get_environment(raster=treatments)
        univar = gscript.parse_command('r.univar', flags='g', map=treatments, env=env)
        if not univar or float(univar['sum']) == 0:
            return 0
        else:
            res = gscript.region(env=env)
            return float(univar['n']) * res['nsres'] * res['ewres']

    def applyTreatments(self, host, host_treated, efficacy, treatment_prefix, env):
        if self.treated_area:
            treatments = gscript.list_grouped(type='raster', pattern=treatment_prefix + '_*')[gscript.gisenv()['MAPSET']]
            treatments = [tr for tr in treatments if int(tr.split('__')[-1]) <= self.currentCheckpoint]
            if len(treatments) >= 2:
                gscript.run_command('r.patch', input=treatments, output='treatments_patched', env=env)
                t = 'treatments_patched'
            elif len(treatments) == 1:
                t = treatments[0]
            gscript.run_command('r.null', map=t, null=0, env=env)
            gscript.mapcalc("{s} = int({l} - {l} * {t} * {e})".format(s=host_treated, t=t,
                                                                      l=host, e=efficacy), env=env)
        else:  # when there is no treatment
            gscript.run_command('g.copy', raster=[host, host_treated], env=env)

    def _run(self):
        self.socket.sendall('cmd:play')

    def _stop(self):
        self.socket.sendall('cmd:end')

    def _isModelRunning(self):
        self.socket.sendall('info:model_running')
        self._threadingEvent.clear()
        self._threadingEvent.wait(2000)
        return self.model_running

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
            res = re.search("_[0-9]{4}_[0-9]{2}_[0-9]{2}", name)
            if res:
                year, month, day = res.group().strip('_').split('_')
                self.currentCheckpoint = int(year) - self.configuration['POPS']['model']['start_time'] + 1
                self.checkpoints[self.currentCheckpoint] = (int(year), int(month), int(day))
                evt2 = updateTimeDisplay(date=(year, month, day))
                self.scaniface.postEvent(self, evt2)

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

        self.currentCheckpoint = 0
        start = self.configuration['POPS']['model']['start_time']
        end = self.configuration['POPS']['model']['end_time']
        self.checkpoints.append((start, 1, 1))
        year = start
        while year <= end:
            self.checkpoints.append((year, 12, 31))
            year += 1

        self.showDisplayChange = True
        self.switchCurrentResult = 0
        self.scaniface.additionalParams4Analyses = {"pops": self.configuration['POPS']}
        self.LoadLayers()
        if self.treatmentSelect.GetValue():
            self.ChangeRegion()

        event = 'tmpevent'
        self.attempt.initialize(event, player=self._createPlayerName())

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
        self.EndSimulation()

    def _bindButtons(self):
        windows = [mapw for mapw in self.giface.GetAllMapDisplays()]
        windows.append(wx.GetTopLevelParent(self))
        windows.append(self.giface.lmgr)
        bindings = {'simulate': self._RunSimulation, 'animate': lambda evt: self.ShowResults(),
                    'stepforward': self.StepForward, 'stepback': self.StepBack}
        if "keyboard_events" in self.configuration:
            items = []
            for eventName in self.configuration['keyboard_events']:
                eventId = wx.NewId()
                items.append((wx.ACCEL_NORMAL, self.configuration['keyboard_events'][eventName], eventId))
                for win in windows:
                    win.Bind(wx.EVT_MENU, bindings.get(eventName, lambda evt: self.CustomAction(eventName)), id=eventId)
            accel_tbl = wx.AcceleratorTable(items)
            for win in windows:
                win.SetAcceleratorTable(accel_tbl)

    def StepBack(self, event):
        self.Step(forward=False)

    def StepForward(self, event):
        self.Step(forward=True)

    def Step(self, forward=True):
        # update time display
        if not self.timeDisplay:
            return
        start = 0
        end = self.configuration['POPS']['model']['end_time'] - self.configuration['POPS']['model']['start_time']
        if forward and self.currentCheckpoint >= end:
            return
        if not forward and self.currentCheckpoint <= start:
            return
        self.currentCheckpoint = self.currentCheckpoint + 1 if forward else self.currentCheckpoint - 1
        displayTime = self.checkpoints[self.currentCheckpoint]
        self.timeDisplay.Update(*displayTime)

        self.ShowResults()

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
        event = self.getEventName()
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
        self.ShowTreatment(self.currentCheckpoint)
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

    def Update(self, year, month, day):
        # TODO: datetime
        label = "{m}/{y}".format(m=month, y=year)
        self.label.SetLabel(label)


class Attempt(object):
    def __init__(self):
        self._currentAttempt = None

    def initialize(self, event, player):
        pattern = "{e}__{n}__[0-9]+_[0-9]+__[0-9]{{4}}_[0-9]{{2}}_[0-9]{{2}}".format(n=player, e=event)
        pattern_layers = gscript.list_grouped(type='raster', pattern=pattern, flag='e')[gscript.gisenv()['MAPSET']]
        if pattern_layers:
            # starting GUI, taking previous saved results - recovering
            name = gscript.natural_sort(pattern_layers)[-1]
            attempt_main, attempt_sub = name.split('__')[-2].split('_')
            # keep main attempt number, sub attempt will be 0
            self._currentAttempt = [int(attempt_main), 0]
        else:
            # fresh, no previous attempts
            self._currentAttempt = [0, 0]

    def increaseMajor(self):
        assert self._currentAttempt is not None
        self._currentAttempt[0] += 1
        self._currentAttempt[1] = 0

    def increaseMinor(self):
        assert self._currentAttempt is not None
        self._currentAttempt[1] += 1

    def getCurrent(self):
        assert self._currentAttempt is not None
        return self._currentAttempt

    def getCurrentFormatted(self, delim):
        assert self._currentAttempt is not None
        return delim.join([str(a) for a in self._currentAttempt])
