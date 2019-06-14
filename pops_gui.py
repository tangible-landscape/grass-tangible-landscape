# -*- coding: utf-8 -*-
"""
@brief POPS GUI

This program is free software under the GNU General Public License
(>=v2). Read the file COPYING that comes with GRASS for details.

@author: Anna Petrasova (akratoc@ncsu.edu)
"""
import os
import json
import imp
import re
import wx
import wx.lib.newevent
import wx.lib.filebrowsebutton as filebrowse
from wx.lib.fancytext import StaticFancyText, RenderToBitmap

from gui_core.gselect import Select
import grass.script as gscript
from grass.pydispatch.signal import Signal
from grass.exceptions import CalledModuleError

from tangible_utils import get_environment, changeLayer

from activities_dashboard import DashboardFrame, MultipleDashboardFrame

from client import SteeringClient
from pops_dashboard import PoPSDashboard


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

        self.timer = wx.Timer(self)
        self.speed = 1000  # 1 second per year
        self.playersByIds = self.playersByName = None
        self.eventsByIds = self.eventsByName = None
        self.configFile = ''
        self.configuration = {}
        self.current = 0
        self.switchCurrentResult = 0
        self.showDisplayChange = True
        self.treatmentHistory = [0] * 50

        self.webDashboard = PoPSDashboard()

        # steering
        self.steeringClient = None
        self.visualizationModes = ['combined', 'singlerun', 'probability']
        self.visualizationMode = 0
        self.empty_placeholders = {'results': 'results_tmp', 'treatments': 'treatments_tmp'}
        self.placeholders = {'results': 'results_tmp', 'treatments': 'treatments_tmp'}
        self.currentCheckpoint = None
        self.checkpoints = []
        self.currentRealityCheckpoint = 0
        self.attempt = Attempt()

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
                    self.tasks = self.configuration['tasks']
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
        visualizationChoice = wx.Choice(modelingBox, choices=self.visualizationModes)
        visualizationChoice.SetSelection(0)

        runBtn.Bind(wx.EVT_BUTTON, lambda evt: self.RunSimulation())
        visualizationChoice.Bind(wx.EVT_CHOICE, self.SwitchVizMode)
        startTreatmentButton.Bind(wx.EVT_BUTTON, lambda evt: self.StartTreatment())
        stopTreatmentButton.Bind(wx.EVT_BUTTON, lambda evt: self.StopTreatment())
        self.treatmentSelect.Bind(wx.EVT_TEXT, lambda evt: self.ChangeRegion())
        defaultRegion.Bind(wx.EVT_BUTTON, self._onDefaultRegion)

        self.Bind(wx.EVT_TIMER, self._simulationResultReady, self.timer)

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
        sizer.Add(visualizationChoice, proportion=1, flag=wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, border=5)
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
        self._connectDashboard()
        self._bindButtons()

    def _connectDashboard(self):
        self.webDashboard.set_root_URL(self.configuration['POPS']['dashboard']['url'])
        self.webDashboard.set_session_id(self.configuration['POPS']['dashboard']['session'])

    def _connectSteering(self):
        if self.steeringClient:
            return
        try:
            urlS = self.configuration['POPS']['steering']['url']
        except KeyError:
            return
        if not urlS:
            return
        server = None
        local_gdbase = False
        steering = False
        steering_dict = self.configuration['POPS']['steering']
        port_simulation = None
        if 'port_simulation' in steering_dict and steering_dict['port_simulation']:
            steering = True
            port_simulation = steering_dict['port_simulation']

        # when we launch server from within, we use the same database
        if 'server' in steering_dict:
            server = steering_dict['server']
            local_gdbase = True
        self.steeringClient = SteeringClient(urlS, port_interface=steering_dict['port_interface'],
                                             port_simulation=port_simulation,
                                             launch_server=server,
                                             local_gdbase=local_gdbase, log=self.giface)
        self.steeringClient.set_on_done(self._afterSimulation)
        self.steeringClient.set_on_step_done(self._uploadStepToDashboard)
        self.steeringClient.set_steering(steering)
        self.steeringClient.connect()

    def OnDisplayUpdate(self, event):
        if not self.dashboardFrame:
            return

        if self.showDisplayChange:
            cumulativeArea = sum(self.treatmentHistory[:self.currentRealityCheckpoint]) + event.area
            cost = self._get_model_param('cost_per_hectare')
            self.dashboardFrame.show_value([event.area / 10000, cumulativeArea / 10000.,
                                            (event.area / 10000) * cost, (cumulativeArea * 10000) * cost])

    def OnTimeDisplayUpdate(self, event):
        if not self.timeDisplay:
            return
        self.timeDisplay.Update(event.current, event.currentView, self.visualizationModes[self.visualizationMode])

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
                self.tasks = self.configuration['tasks']
        else:
            self.settings['activities']['config'] = ''

    def _get_model_param(self, param):
        if self.params_from_dashboard:
            return self.params_from_dashboard[param]
        else:
            if param in self.configuration['POPS']['model']:
                return self.configuration['POPS']['model'][param]
            else:
                return self.configuration['POPS'][param]

    def _debug(self, msg):
        with open('/tmp/debug.txt', 'a+') as f:
            f.write(msg)
            f.write('\n')

    def _afterSimulation(self, name):
        self._renameAllAfterSimulation(name)
        evt = updateInfoBar(dismiss=True, message=None)
        wx.PostEvent(self, evt)
        self.webDashboard.run_done()

    def _uploadStepToDashboard(self, name):
        if not 'probability' in name:
            return

        res = re.search('[0-9]{4}_[0-9]{2}_[0-9]{2}', name)
        if res:
            date = res.group()
            year = int(date.split('_')[0])
            print self.webDashboard.upload_results(year, name)

    def _renameAllAfterSimulation(self, name):
        name_split = name.split('__')
        if len(name_split) == 3:
            event, player, date = name.split('__')
        elif len(name_split) == 4:  # probability
            prob, event, player, date = name.split('__')
        a1, a2 = self.attempt.getCurrent()
        pattern = "{e}__{n}__[0-9]{{4}}_[0-9]{{2}}_[0-9]{{2}}".format(n=player, e=event)
        pattern_layers = gscript.list_grouped(type='raster', pattern=pattern, flag='e')[gscript.gisenv()['MAPSET']]
        if pattern_layers:
            for layer in pattern_layers:
                components = layer.split('__')
                new_name = '__'.join(components[:-1] + ['{a1}_{a2}'.format(a1=a1, a2=a2)] + components[-1:])
                gscript.run_command('g.copy', raster=[layer, new_name], quiet=True, overwrite=True)

    def SwitchVizMode(self, event=None):
        # clear the queue to stop animation
        self.steeringClient.results_clear()

        if event:
            # from gui
            self.visualizationMode = event.GetSelection()
        else:
            # from button
            self.visualizationMode += 1
            if self.visualizationMode >= len(self.visualizationModes):
                self.visualizationMode = 0

        if self.timeDisplay:
            self.timeDisplay.Update(self.currentRealityCheckpoint, self.currentCheckpoint, self.visualizationModes[self.visualizationMode])

        self.ShowResults()

    def _createPlayerName(self):
        return 'player'

    def getEventName(self):
        return 'tmpevent'

    def _ifShowProbability(self, evalFuture=False):
        if self.visualizationModes[self.visualizationMode] == 'singlerun':
            return False
        if self.visualizationModes[self.visualizationMode] == 'probability':
            return True
        if self.visualizationModes[self.visualizationMode] == 'combined':
            if self.currentCheckpoint + (1 if evalFuture else 0) > self.currentRealityCheckpoint:
                return True
            return False

    def ShowResults(self):
        # change layers
        self.ShowTreatment()
        displayTime = self.checkpoints[self.currentCheckpoint]
        event = 'tmpevent'
        attempt = self.attempt.getCurrentFormatted(delim='_')
        name = self._createPlayerName()
        prefix = "{e}__{n}__{a}__".format(n=name, e=event, a=attempt)
        prefix_prob = self.configuration['POPS']['model']['probability_series'] + '__' + prefix
        suffix = "{y}_{m:02d}_{d:02d}".format(y=displayTime[0], m=displayTime[1], d=displayTime[2])

        if self._ifShowProbability():
            rules = self.configuration['POPS']['color_probability']
            name = prefix_prob + suffix
        else:
            rules = self.configuration['POPS']['color_trees']
            name = prefix + suffix

        if self.currentRealityCheckpoint == 0:
            name = ''

        f = gscript.find_file(name=name, element='raster')
        if not f['fullname']:
            # display empty raster
            self._changeResultsLayer(cmd=['d.rast', 'map=' + self.empty_placeholders['results']],
                                     name=self.empty_placeholders['results'], resultType='results', useEvent=False)
        else:
            try:
                # need to set the colors, sometimes color tables are not copied
                # flag w will end in error if there is already table
                gscript.run_command('r.colors', map=name, quiet=True, rules=rules, flags='w')
            except CalledModuleError:
                pass
            cmd = ['d.rast', 'values=0', 'flags=i', 'map={}'.format(name)]
            self._changeResultsLayer(cmd=cmd, name=name, resultType='results', useEvent=False)

    def ShowTreatment(self):
        event = self.getEventName()
        attempt = str(self.attempt.getCurrent()[0])
        name = self._createPlayerName()
        name = '__'.join([self.configuration['POPS']['treatments'], event, name, attempt])
        cmd = ['d.vect', 'map={}'.format(name), 'display=shape,cat', 'fill_color=none', 'width=2',
               'label_color=black', 'label_size=12', 'xref=center', 'yref=bottom', 'font=n019044l']

        self._changeResultsLayer(cmd=cmd, name=name, resultType='treatments', useEvent=False)

    def _RunSimulation(self, event=None):
        print '_runSimulation'
        if self.switchCurrentResult == 0:
            # it's allowed to interact now
            # just to be sure remove results
            self.HideResultsLayers()
            wx.FutureCall(self.configuration['POPS']['waitBeforeRun'], self.RunSimulation)

    def EndSimulation(self):
        if self.steeringClient and self.steeringClient.simulation_is_running():
            self.steeringClient.simulation_stop()

    def InitSimulation(self):
        self._initSimulation(restart=False)
        self.attempt.increaseMajor()
        self.HideResultsLayers()

    def RestartSimulation(self):
        self._initSimulation(restart=True)
        self.attempt.increaseMajor()
        self.HideResultsLayers()

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
        region = {'n': extent['north'], 's': extent['south'], 'w': extent['west'], 'e': extent['east'], 'align': host}
        region = '{n},{s},{w},{e},{align}'.format(**region)
        model_params = self.configuration['POPS']['model'].copy()
        model_name = model_params.pop('model_name')
        flags = model_params.pop('flags')
        model_params.update({'output_series': postfix,
                             'probability_series': probability})

        model_params['short_distance_scale'] = self.params_from_dashboard['distance_scale']
        model_params['reproductive_rate'] = self.params_from_dashboard['reproductive_rate']
        model_params['random_seed'] = self.params_from_dashboard['random_seed']

        # run simulation
        self.steeringClient.simulation_set_params(model_name, model_params, flags, region)
        self.steeringClient.simulation_start(restart)

    def RunSimulation(self, event=None):
        self.params_from_dashboard = self.webDashboard.get_run_params()

        if self.steeringClient.simulation_is_running():
            # if simulation in the beginning, increase major version and restart the simulation
            if self.currentCheckpoint == 0:
                self.RestartSimulation()
            else:
                self.attempt.increaseMinor()
        else:
            self.InitSimulation()


        #self.showDisplayChange = False

        self.infoBar.ShowMessage("Running...")
        playerName = self._createPlayerName()
        new_attempt = self.attempt.getCurrent()
        print new_attempt

        # grab a new raster of conditions
        # process new input layer
        treatments = self.configuration['POPS']['treatments']
        treatments_resampled = treatments + '_resampled'
        studyArea = self.configuration['tasks'][self.current]['base']
        host = self.configuration['POPS']['model']['host']
        probability = self.configuration['POPS']['model']['probability_series']
        treatment_efficacy = self._get_model_param('efficacy')
        cost_per_hectare = self._get_model_param('cost_per_hectare')

        env = get_environment(raster=studyArea, align=host)

        event = 'tmpevent'
        postfix = 'tmpevent' + '__' + playerName + '_'
        probability = probability + '__' + postfix
        # todo, save treatments
        tr_name = '__'.join([treatments, event, playerName, "{a1}".format(a1=new_attempt[0]),
                             str(max(0, self.currentCheckpoint))])
        gscript.run_command('g.copy', raster=[treatments, tr_name], env=env)
        # create treatment vector of all used treatments in that scenario
        tr_vector = self.createTreatmentVector(tr_name, env=env)
        self.webDashboard.set_management_polygons(tr_vector)
        self.webDashboard.update_run()

        # measuring area
        gscript.mapcalc("{n} = if (isnull({t}) || {host} == 0, null(), {t}) ".format(host=host, t=treatments, n=treatments + '_exclude_host'), env=env)
        self.treated_area = self.computeTreatmentArea(treatments + '_exclude_host')
        self.treatmentHistory[self.currentCheckpoint] = self.treated_area
        self.money_spent = (self.treated_area / 10000.) * cost_per_hectare


        # compute proportion - disable for now
        resampling_treatments = False
        if resampling_treatments:
            if gscript.raster_info(tr_name)['ewres'] < gscript.raster_info(host)['ewres']:
                gscript.run_command('r.resamp.stats', input=tr_name, output=treatments_resampled, flags='w', method='count', env=env)
                maxvalue = gscript.raster_info(treatments_resampled)['max']
                gscript.mapcalc("{p} = if(isnull({t}), 0, {t} / {m})".format(p=treatments_resampled + '_proportion', t=treatments_resampled, m=maxvalue), env=env)
                gscript.run_command('g.rename', raster=[treatments_resampled + '_proportion', treatments_resampled], env=env)
            else:
                gscript.run_command('r.resamp.stats', input=tr_name, output=treatments_resampled, flags='w', method='average', env=env)
                gscript.run_command('r.null', map=treatments_resampled, null=0, env=env)
        else:
            gscript.run_command('r.null', map=tr_name, null=0, env=env)
            gscript.mapcalc("{tr_new} = float({tr}) / {eff}".format(tr_new=tr_name + '_efficacy', tr=tr_name, eff=treatment_efficacy))
            gscript.run_command('g.rename', raster=[tr_name + '_efficacy', tr_name], env=env)

        self.currentRealityCheckpoint = self.currentCheckpoint + 1

        # export treatments file to server
        self.steeringClient.simulation_send_data(tr_name, tr_name, env)
        # load new data here
        tr_year = self.configuration['POPS']['model']['start_time'] + self.currentCheckpoint
        self.steeringClient.simulation_load_data(tr_year, tr_name)

        self.steeringClient.simulation_goto(self.currentCheckpoint)

        if self.visualizationModes[self.visualizationMode] != 'probability':
            self.steeringClient.simulation_sync_runs()

        self.steeringClient.simulation_play()

        self.HideResultsLayers()
        self.ShowTreatment()

    def createTreatmentVector(self, treatment_layer, env):
        tr, evt, plr, attempt, year = treatment_layer.split('__')
        postfix = 'cat_year'
        gscript.write_command('r.reclass', input=treatment_layer, output=treatment_layer + '__' + postfix, rules='-',
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
            gscript.run_command('g.copy', raster=[treatment_layer + '__' + postfix, name], env=env)
        gscript.run_command('r.to.vect', input=name, output=name, flags='vt', type='area', env=env)
        gscript.run_command('v.colors', map=name, use='cat', color=self.configuration['POPS']['color_treatments'], env=env)
        return name
        # for nicer look
        #gscript.run_command('v.generalize', input=name + '_tmp', output=name, method='snakes', threshold=10, env=env)

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
        self.steeringClient.simulation_play()

    def _stop(self):
        self.steeringClient.simulation_stop()

    def _simulationResultReady(self, event):
        if not self.steeringClient.results_empty():
            found = False
            while not found and not self.steeringClient.results_empty():
                name = self.steeringClient.results_get()
                isProb = self._ifShowProbability(evalFuture=True)
                if self.configuration['POPS']['model']['probability_series'] in name and isProb:
                    found = True
                    rules = self.configuration['POPS']['color_probability']
                elif not (self.configuration['POPS']['model']['probability_series']  in name or isProb):
                    found = True
                    rules = self.configuration['POPS']['color_trees']
                else:
                    continue
                gscript.run_command('r.colors', map=name, quiet=True, rules=rules)
                cmd = ['d.rast', 'values=0', 'flags=i', 'map={}'.format(name)]

                # update year
                res = re.search("_[0-9]{4}_[0-9]{2}_[0-9]{2}", name)
                if res:  # should happen always?
                    year, month, day = res.group().strip('_').split('_')
                    # if last checkpoint is the same date as current raster, we don't want it
                    if self.checkpoints[self.currentCheckpoint] == (int(year), int(month), int(day)):
                        return
                    self.currentCheckpoint = int(year) - self.configuration['POPS']['model']['start_time'] + 1
                    self.checkpoints[self.currentCheckpoint] = (int(year), int(month), int(day))
                    evt = updateTimeDisplay(current=self.currentRealityCheckpoint,
                                            currentView=self.currentCheckpoint,
                                            vtype=self.visualizationModes[self.visualizationMode])
                    self.scaniface.postEvent(self, evt)

                self._changeResultsLayer(cmd=cmd, name=name, resultType='results', useEvent=True)

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
        if self.steeringClient:
            self.steeringClient.disconnect()
            self.steeringClient.stop_server()
        if self.webDashboard:
            self.webDashboard.close()

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
        self.AddTempLayers()
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
        self.placeholders = {'results': 'results_tmp', 'treatments': 'treatments_tmp'}
        self._stopScanning()
        self.timer.Stop()
        self.EndSimulation()
        self.currentCheckpoint = self.currentRealityCheckpoint = 0

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

        self.steeringClient.results_clear()

        start = 0
        end = self.configuration['POPS']['model']['end_time'] - self.configuration['POPS']['model']['start_time'] + 1
        if forward and self.currentCheckpoint >= end:
            return
        if not forward and self.currentCheckpoint <= start:
            return
        self.currentCheckpoint = self.currentCheckpoint + 1 if forward else self.currentCheckpoint - 1
        self.timeDisplay.Update(self.currentRealityCheckpoint, self.currentCheckpoint, self.visualizationModes[self.visualizationMode])

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

    def AddTempLayers(self):
        # create empty placeholders
        f = gscript.find_file(name=self.placeholders['results'], element='raster')
        if not f['fullname']:
            env = get_environment(raster=self.configuration['tasks'][self.current]['base'])
            gscript.mapcalc(self.empty_placeholders['results'] + " = null()", env=env)
            gscript.run_command('v.edit', tool='create', map=self.empty_placeholders['treatments'], env=env)

        ll = self.giface.GetLayerList()
        ll.AddLayer('raster', name=self.empty_placeholders['results'],
                    cmd=['d.rast', 'map=' + self.empty_placeholders['results']], checked=True)
        ll.AddLayer('vector', name=self.empty_placeholders['treatments'],
                    cmd=['d.vect', 'map=' + self.empty_placeholders['treatments']], checked=True)

    def LoadLayers(self):
        ll = self.giface.GetLayerList()
        for i, cmd in enumerate(self.configuration['tasks'][self.current]['layers']):
            opacity = 1.0
            checked = True
            if "layers_opacity" in self.configuration['tasks'][self.current]:
                opacity_list = self.configuration['tasks'][self.current]['layers_opacity']
                if i < len(opacity_list):
                    opacity = float(opacity_list[i])
                else:
                    self.giface.WriteWarning("Number of layers is larger than the number of opacity values in config file")
            if "layers_checked" in self.configuration['tasks'][self.current]:
                checked_list = self.configuration['tasks'][self.current]['layers_checked']
                if i < len(checked_list):
                    checked = checked_list[i]
                else:
                    self.giface.WriteWarning("Number of layers is larger than the number of checked values in config file")
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
            elif cmd[0] == 'd.barscale':
                l = ll.AddLayer('barscale', name=cmd[1].split('=')[1], checked=checked,
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

    def _changeResultsLayer(self, cmd, name, resultType, useEvent):
        ll = self.giface.GetLayerList()
        if not hasattr(ll, 'ChangeLayer'):
            print "Changing layer in Layer Manager requires GRASS GIS version > 7.8"
            return
        # TODO: check there is exactly one layer
        pl_layer = ll.GetLayersByName(self.placeholders[resultType])[0]

        if useEvent:
            evt = changeLayer(layer=pl_layer, cmd=cmd)
            self.scaniface.postEvent(self.scaniface, evt)
        else:
            ll.ChangeLayer(pl_layer, cmd=cmd)
        self.placeholders[resultType] = name

    def HideResultsLayers(self, useEvent=False):
        self._changeResultsLayer(cmd=['d.rast', 'map=' + self.empty_placeholders['results']],
                                 name=self.empty_placeholders['results'], resultType='results', useEvent=useEvent)
        self._changeResultsLayer(cmd=['d.vect', 'map=' + self.empty_placeholders['treatments']],
                                 name=self.empty_placeholders['treatments'], resultType='treatments', useEvent=useEvent)

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

    def StartDisplay(self):
        multiple = False if 'multiple' not in self.tasks[self.current]['display'] else self.tasks[self.current]['display']['multiple']
        title = None if 'title' not in self.tasks[self.current]['display'] else self.tasks[self.current]['display']['title']
        vertical = False if 'vertical' not in self.tasks[self.current]['display'] else self.tasks[self.current]['display']['vertical']
        fontsize = self.tasks[self.current]['display']['fontsize']
        average = self.tasks[self.current]['display']['average']
        maximum = self.tasks[self.current]['display']['maximum']
        formatting_string = self.tasks[self.current]['display']['formatting_string']
        if multiple:
            self.dashboardFrame = MultipleDashboardFrame(self, fontsize=fontsize, average=average, maximum=maximum,
                                                     title=title, formatting_string=formatting_string, vertical=vertical)
        else:
            self.dashboardFrame = DashboardFrame(self, fontsize=fontsize, average=average, maximum=maximum, title=title, formatting_string=formatting_string)


        pos = self._getDashboardPosition(key='display')
        size = self._getDashboardSize(key='display')
        self.dashboardFrame.SetSize(size)
        self.dashboardFrame.Show()
        self.dashboardFrame.SetPosition(pos)

    def _getDashboardPosition(self, key):
        if 'position' in self.tasks[self.current][key]:
            pos = self.tasks[self.current][key]['position']
        elif 'relative_position' in self.tasks[self.current][key]:
            relPos = self.tasks[self.current][key]['relative_position']
            pos = self._getPosFromRelative(relPos)
        else:
            pos = self._getPosFromRelative((1.01, 0.5))
        return pos

    def _getDashboardSize(self, key):
        if 'size' in self.tasks[self.current][key]:
            size = self.tasks[self.current][key]['size']
        elif 'relative_size' in self.tasks[self.current][key]:
            relSize = self.tasks[self.current][key]['relative_size']
            size = self._getSizeFromRelative(relSize)
        else:
            size = self._getSizeFromRelative((0.3, 0.3))
        return size

    def _getPosFromRelative(self, pos):
        md = self.giface.GetMapDisplay()
        mdSize = md.GetSize()
        mdPos = md.GetPosition()
        return (mdPos[0] + pos[0] * mdSize[0], mdPos[1] + pos[1] * mdSize[1])

    def _getSizeFromRelative(self, size):
        md = self.giface.GetMapDisplay()
        mdSize = md.GetSize()
        return (size[0] * mdSize[0], size[1] * mdSize[1])

    def StartTimeDisplay(self):
        self.timeDisplay = TimeDisplay(self, start=self.configuration['POPS']['model']['start_time'],
                                       end=self.configuration['POPS']['model']['end_time'] + 1,
                                       fontsize=self.configuration['tasks'][self.current]['time_display']['fontsize'],
                                       vtype=self.visualizationModes[self.visualizationMode])

        pos = self._getDashboardPosition(key='time_display')
        size = self._getDashboardSize(key='time_display')
        self.timeDisplay.SetSize(size)
        self.timeDisplay.Show()
        self.timeDisplay.SetPosition(pos)
#        evt = updateTimeDisplay(date=(self.configuration['POPS']['model']['start_time'], 1, 1))
        evt = updateTimeDisplay(current=self.currentRealityCheckpoint,
                                currentView=self.currentCheckpoint,
                                vtype=self.visualizationModes[self.visualizationMode])
        self.scaniface.postEvent(self, evt)


class SimpleTimeDisplay(wx.Frame):
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
        if str(month) == '12':
            year = int(year) + 1
        self.label.SetLabel("{y} ".format(y=year))


class TimeDisplay(wx.Frame):
    def __init__(self, parent, fontsize, start, end, vtype):
        wx.Frame.__init__(self, parent=parent, style=wx.NO_BORDER)
        self.years = range(start, end + 1)
        self.fontsize = fontsize
        text = self.GenerateHTML(0, start, vtype)
        self.textCtrl = StaticFancyText(self, -1, text)
        self.sizer = wx.BoxSizer(wx.VERTICAL)
        self.sizer.Add(self.textCtrl, 1, wx.ALL | wx.ALIGN_CENTER | wx.EXPAND, 5)
        self.SetSizer(self.sizer)
        self.sizer.Fit(self)

    def Update(self, current, currentView, vtype):
        text = self.GenerateHTML(current + self.years[0], currentView + self.years[0], vtype)
        bmp = RenderToBitmap(text)
        self.textCtrl.SetBitmap(bmp)

    def GenerateHTML(self, current, currentView, vtype):
        delim_single = '&#9148;'
        delim_prob = '&#9776;'
        delim_split = '&#9887;'
        html = ''
        style = {'lastTreatment': 'weight="bold" color="black" size="{}"'.format(self.fontsize),
                 'currentView':  'weight="bold" color="black" size="{}"'.format(int(self.fontsize * 1.5)),
                 'default': 'weight="bold" color="gray" size="{}"'.format(self.fontsize)}
        for year in self.years:
            if year == currentView:
                styl = style['currentView']
            elif year == current:
                styl = style['lastTreatment']
            else:
                styl = style['default']
            html += ' <font {style}>{year}</font> '.format(year=year, style=styl)
            if year != self.years[-1]:
                d = delim_single
                if vtype == 'probability':
                    if year == self.years[0]:
                        d = delim_split
                    else:
                        d = delim_prob
                elif vtype == 'combined':
                    # TODO fix None
                    if year == current:
                        d = delim_split
                    elif year > current:
                        d = delim_prob
                # for now, keep simple until I figure it out
                #d = delim_single
                html += '<font {style}> {d} </font>'.format(style=style['default'], d=d)
        return html


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
