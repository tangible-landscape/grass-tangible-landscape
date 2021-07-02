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
from wxasync import StartCoroutine

from gui_core.gselect import Select
import grass.script as gscript
from grass.pydispatch.signal import Signal
from grass.exceptions import CalledModuleError

from tangible_utils import get_environment, changeLayer, checkLayers

from activities_dashboard import MultipleHTMLDashboardFrame

from client import SteeringClient, EVT_PROCESS_FOR_DASHBOARD_EVENT, EVT_BASELINE_DONE
from pops_dashboard import PoPSDashboard, ModelParameters, \
    dateFromString, dateToString
from pops_treatments import Treatments
from time_display import SteeringDisplayFrame, CurrentViewDisplayFrame


updateDisplay, EVT_UPDATE_DISPLAY = wx.lib.newevent.NewEvent()
updateTimeDisplay, EVT_UPDATE_TIME_DISPLAY = wx.lib.newevent.NewEvent()
updateInfoBar, EVT_UPDATE_INFOBAR = wx.lib.newevent.NewEvent()


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
        self.configFile = ''
        self.configuration = {}
        self.workdir = None
        self.current = 0
        self.switchCurrentResult = 0
        self.showDisplayChange = True
        self.treatmentHistory = [0] * 50

        self.webDashboard = None
        self.wsWebDashboard = None
        self.params = ModelParameters()

        # steering
        self.steeringClient = None
        self.visualizationModes = ['singlerun', 'probability', 'combined']
        self.visualizationMode = 0
        self.empty_placeholders = {'results': 'results_tmp', 'treatments': 'treatments_tmp'}
        self.placeholders = {'results': 'results_tmp', 'treatments': 'treatments_tmp'}
        self._zoomName = "zoomed"
        self.currentCheckpoint = None
        self.checkpoints = []
        self.currentRealityCheckpoint = 0
        self.attempt = Attempt()
        self._one_step = None

        self.profileFrame = self.dashboardFrame = self.timeDisplay = self.timeStatusDisplay = None

        self.treated_area = 0
        self.money_spent = 0

        self.env = os.environ.copy()
        self.env['GRASS_OVERWRITE'] = '1'
        self.env['GRASS_VERBOSE'] = '0'
        self.env['GRASS_MESSAGE_FORMAT'] = 'standard'

        if 'POPS' not in self.settings:
            self.settings['POPS'] = {}
            self.settings['POPS']['config'] = ''
        else:
            self.configFile = self.settings['POPS']['config']
            self.workdir = os.path.dirname(self.configFile)


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

        self.treatments = Treatments(study_area=self.configuration['tasks'][self.current]['base'],
                                     workdir=self.workdir)

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
        self.visualizationChoice = wx.Choice(modelingBox, choices=self.visualizationModes)
        self.visualizationChoice.SetSelection(0)
        baselineButton = wx.Button(modelingBox, label="Baseline")
        baselineButton.Bind(wx.EVT_BUTTON, self.RunBaseline)
        resetButton = wx.Button(modelingBox, label=u"\u21A9")
        resetButton.Bind(wx.EVT_BUTTON, self.ResetSimulation)
        self.replaySelect = Select(modelingBox, size=(-1, -1), type='raster', fullyQualified=False)

        runBtn.Bind(wx.EVT_BUTTON, lambda evt: self.RunSimulation())
        self.visualizationChoice.Bind(wx.EVT_CHOICE, self.SwitchVizMode)
        startTreatmentButton.Bind(wx.EVT_BUTTON, lambda evt: self.StartTreatment())
        stopTreatmentButton.Bind(wx.EVT_BUTTON, lambda evt: self.StopTreatment())
        self.treatmentSelect.Bind(wx.EVT_TEXT, lambda evt: self.ChangeRegion())
        defaultRegion.Bind(wx.EVT_BUTTON, self._onDefaultRegion)

        self.Bind(wx.EVT_TIMER, self._simulationResultReady, self.timer)
        self.Bind(wx.EVT_TIMER, self._checkDynamicZoom, self.timer)

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
        sizer.Add(self.visualizationChoice, proportion=1, flag=wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, border=5)
        sizer.Add(baselineButton, proportion=0, flag=wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, border=5)
        sizer.Add(resetButton, proportion=0, flag=wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, border=5)
        boxSizer.Add(sizer, flag=wx.EXPAND | wx.ALL, border=5)

        sizer = wx.BoxSizer(wx.HORIZONTAL)
        sizer.Add(wx.StaticText(modelingBox, label="Treatment area:"), flag=wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, border=5)
        sizer.Add(self.treatmentSelect, proportion=1, flag=wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, border=5)
        sizer.Add(defaultRegion, proportion=0, flag=wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, border=5)
        boxSizer.Add(sizer, flag=wx.EXPAND | wx.ALL, border=5)

        sizer = wx.BoxSizer(wx.HORIZONTAL)
        sizer.Add(wx.StaticText(modelingBox, label="Replay scenario:"), flag=wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, border=5)
        sizer.Add(self.replaySelect, proportion=1, flag=wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, border=5)
        boxSizer.Add(sizer, flag=wx.EXPAND | wx.ALL, border=5)

        self.mainSizer.Add(boxSizer, flag=wx.EXPAND | wx.ALL, border=5)

        self.SetSizer(self.mainSizer)
        self.mainSizer.Fit(self)

        self._bindButtons()

        self.Bind(EVT_UPDATE_DISPLAY, self.OnDisplayUpdate)
        self.Bind(EVT_PROCESS_FOR_DASHBOARD_EVENT, self._uploadStepToDashboard)
        self.Bind(EVT_BASELINE_DONE, self._baselineDone)
        self.Bind(EVT_UPDATE_TIME_DISPLAY, self.OnTimeDisplayUpdate)
        self.Bind(EVT_UPDATE_INFOBAR, self.OnUpdateInfoBar)

    def IsStandalone(self):
        """If TL plugin runs standalone without GUI"""
        if self.giface.GetLayerTree():
            return False
        return True

    def _connect(self):
        self._connectSteering()
        if 'dashboard' in self.configuration['POPS'] and self.configuration['POPS']['dashboard']:
            self._connectDashboard()
        self._bindButtons()

    def _connectDashboard(self):
        dashboard = self.configuration['POPS']['dashboard']
        self.webDashboard = PoPSDashboard()
        self.params.set_web_dashboard(self.webDashboard)
        self.webDashboard.initialize(dashboard)
        StartCoroutine(self.webDashboard.connect, self)

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
            server = os.path.join(os.path.dirname(os.path.realpath(__file__)), server)
            local_gdbase = True
        self.steeringClient = SteeringClient(urlS, port_interface=steering_dict['port_interface'],
                                             port_simulation=port_simulation,
                                             launch_server=server,
                                             local_gdbase=local_gdbase, log=self.giface, eventHandler=self)
        self.steeringClient.set_on_done(self._afterSimulation)
        self.steeringClient.set_steering(steering)
        self.steeringClient.connect()

    def _initVisualizationModes(self):
        if self.steeringClient:
            if self.steeringClient.is_steering():
                self.visualizationChoice.SetItems(self.visualizationModes)
                self.visualizationMode = 2
            else:
                # only probability (default) and single run
                self.visualizationChoice.SetItems(self.visualizationModes[:-1])
                self.visualizationMode = 1
            self.visualizationChoice.SetSelection(self.visualizationMode)

    def OnDisplayUpdate(self, event):
        if not self.dashboardFrame:
            return

        if self.showDisplayChange:
            cumulativeArea = sum(self.treatmentHistory[:self.currentRealityCheckpoint]) + event.area
            cost = float(self.params.pops['cost_per_meter_squared'])
            unit = self.configuration['POPS'].get('unit', 'acre')
            if unit == 'acre':
                coef = 4046.86
            elif unit == 'ha':
                coef = 10000.
            elif unit == 'km':
                coef = 1000000.
            else:
                coef = 1.
            money_coef = self.configuration['POPS'].get('cost_unit', 1)
            if self.steeringClient.is_steering():
                self.dashboardFrame.show_value([event.area / coef,
                                                event.area * cost / money_coef,
                                                cumulativeArea / coef,
                                                cumulativeArea * cost / money_coef])
            else:
                self.dashboardFrame.show_value([event.area / coef, event.area * cost / money_coef])

    def OnTimeDisplayUpdate(self, event):
        if self.timeDisplay:
            self.timeDisplay.UpdateText(event.current, event.currentView, self.visualizationModes[self.visualizationMode])
        if self.timeStatusDisplay:
            self.timeStatusDisplay.UpdateText(event.currentView, "forecast" if self._ifShowProbability() else "occurrence")

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
            self.workdir = os.path.dirname(self.configFile)
            self.params.set_config(self.configuration['POPS'], self.workdir)
        else:
            self.settings['POPS']['config'] = ''

    def _debug(self, msg):
        with open('/tmp/debug.txt', 'a+') as f:
            f.write(msg)
            f.write('\n')

    def _afterSimulation(self, name):
        new_layers = self._renameAllAfterSimulation(name)
        #if new_layers:
        #    self._computeDifference(new_layers)
        evt = updateInfoBar(dismiss=True, message=None)
        wx.PostEvent(self, evt)
        res = re.search('[0-9]{4}_[0-9]{2}_[0-9]{2}', name)
        if res and self.webDashboard:
            self.webDashboard.run_done(last_name_suffix=res.group())

    def _uploadStepToDashboard(self, event):
        if not event.name.startswith(self.params.model['probability_series']):
            return

        res = re.search('[0-9]{4}_[0-9]{2}_[0-9]{2}', event.name)
        if res:
            date = res.group()
            year = int(date.split('_')[0])
            # assumes infected is already ready
            remove = self.params.model['probability_series'] + '__'
            single_infected = event.name[len(remove):]
            average_infected = '__'.join([self.params.model['average_series'], single_infected])
            spread_file = self.params.model['spread_rate_output']
            if self.webDashboard:
                checkpoint = int(year) - dateFromString(self.params.model['start_date']).year + 1
                if checkpoint > self.currentRealityCheckpoint:
                    use_single = False
                else:
                    use_single = True
                rotation = 0
                if 'rotation' in self.params.pops:
                    rotation = self.params.pops['rotation']
                self.webDashboard.upload_results(year, event.name, single_infected, average_infected,
                                                 spread_file, rotation, use_single=use_single)

    def _processWSInfo(self, data):
        self.infoBar.ShowMessage("PoPS Web is saying: " + str(data))

    def _computeDifference(self, names):
        difference = self.configuration['POPS']['difference']
        env = get_environment(raster=names[0])
        resulting = []
        for each in names:
            name_split = each.split('__')
            if len(name_split) == 4:
                event, player, att, date = each.split('__')
                prob = ''
            elif len(name_split) == 5:  # probability
                prob, event, player, att, date = each.split('__')
            else:
                return
            major, minor = att.split('_')
            if minor == '0':
                return
            minor = int(minor) - 1
            att_prev = "{a1}_{a2}".format(a1=major, a2=minor)
            if prob:
                new_name = '__'.join((difference, prob, event, player, att, date))
                previous = '__'.join((prob, event, player, att_prev, date))
            else:
                new_name = '__'.join((difference, event, player, att, date))
                previous = '__'.join((event, player, att_prev, date))
            try:
                gscript.mapcalc("{n} = {c} - {p}".format(n=new_name, c=each, p=previous), env=env)
            except CalledModuleError:
                print('difference computation failed')
                continue
            resulting.append(new_name)
        gscript.run_command('r.colors', maps=','.join(resulting), env=env)

    def _renameAllAfterSimulation(self, name):
        name_split = name.split('__')
        if len(name_split) == 3:
            event, player, date = name.split('__')
        elif len(name_split) == 4:  # probability or avg
            prob, event, player, date = name.split('__')
        else:
            player = 'player'
            event = 'tmpevent'
        a1, a2 = self.attempt.getCurrent()
        pattern = "{e}__{n}__[0-9]{{4}}_[0-9]{{2}}_[0-9]{{2}}".format(n=player, e=event)
        pattern_layers = gscript.list_grouped(type='raster', pattern=pattern, flag='e')[gscript.gisenv()['MAPSET']]
        new_names = []
        if pattern_layers:
            for layer in pattern_layers:
                components = layer.split('__')
                new_name = '__'.join(components[:-1] + ['{a1}_{a2}'.format(a1=a1, a2=a2)] + components[-1:])
                gscript.run_command('g.copy', raster=[layer, new_name], quiet=True, overwrite=True)
                new_names.append(new_name)
        return new_names

    def SwitchVizMode(self, event=None):
        # clear the queue to stop animation
        if self.steeringClient:
            self.steeringClient.results_clear()

        if event:
            # from gui
            self.visualizationMode = event.GetSelection()
        else:
            # from button
            if self.steeringClient and self.steeringClient.is_steering():
                self.visualizationMode += 1
                if self.visualizationMode >= len(self.visualizationModes):
                    self.visualizationMode = 0
            else:
                self.visualizationMode += 1
                if self.visualizationMode >= len(self.visualizationModes) - 1:
                    self.visualizationMode = 0
                self.visualizationChoice.SetSelection(self.visualizationMode)

        if self.timeDisplay:
            self.timeDisplay.UpdateText(self.currentRealityCheckpoint, self.currentCheckpoint, self.visualizationModes[self.visualizationMode])

        if self.timeStatusDisplay:
            self.timeStatusDisplay.UpdateText(self.currentCheckpoint, "forecast" if self._ifShowProbability() else "occurrence")

        self.ShowResults()

    def _createPlayerName(self):
        if self.webDashboard:
            name = self.webDashboard.runcollection_name()
            if name:
                name = name.replace('-', '_').replace('.', '_').replace('__', '_').replace(':', '_').replace(' ', '_')
                return name
            else:
                return 'run'
        return 'run'

    def getEventName(self):
        if self.webDashboard:
            name = self.webDashboard.get_session_name()
            if name:
                name = name.replace('-', '_').replace('.', '_').replace('__', '_').replace(':', '_').replace(' ', '_')
                return name
            else:
                return 'tmpevent'
        else:
            return 'tmpevent'

    def _ifShowProbability(self, evalFuture=False):
        if self.visualizationModes[self.visualizationMode] == 'singlerun':
            return False
        if self.visualizationModes[self.visualizationMode] == 'probability':
            if self.currentCheckpoint == 0:
                return False
            return True
        if self.visualizationModes[self.visualizationMode] == 'combined':
            if self.currentCheckpoint + (1 if evalFuture else 0) > self.currentRealityCheckpoint:
                return True
            return False

    def ResetSimulation(self, event):
        self.HideResultsLayers()
        self.ShowInitalInfection(useEvent=False, show=True)
        self.currentCheckpoint = 0
        self.currentRealityCheckpoint = 0
        self.treatmentHistory = [0] * 50
        if self.timeDisplay:
            self.timeDisplay.UpdateText(self.currentRealityCheckpoint, self.currentCheckpoint, self.visualizationModes[self.visualizationMode])
        if self.timeStatusDisplay:
            self.timeStatusDisplay.UpdateText(self.currentCheckpoint, "forecast" if self._ifShowProbability() else "occurrence")
        if self.webDashboard:
            # call this after running through all steps?
            self.webDashboard.report_runcollection_status(success=True)
        event.Skip()

    def Replay(self, scenario):
        displayTime = self.checkpoints[self.currentCheckpoint]
        suffix = "{y}_{m:02d}_{d:02d}".format(y=displayTime[0], m=displayTime[1], d=displayTime[2])
        res = re.search("__[0-9]{4}_[0-9]{2}_[0-9]{2}", scenario)
        if res:
            scenario = scenario.replace(res.group(), '')
        name = scenario + '__' + suffix
        if self.currentCheckpoint == 0:
            self.ShowInitalInfection(useEvent=False, show=True)
        else:
            self.ShowInitalInfection(useEvent=False, show=False)

        f = gscript.find_file(name=name, element='raster')
        if not f['fullname']:
            # display empty raster
            self.HideResultsLayers()
        else:
            if name.startswith(self.params.model['probability_series']):
                rules = os.path.join(self.workdir, self.configuration['POPS']['color_probability'])
            else:
                rules = os.path.join(self.workdir, self.configuration['POPS']['color_trees'])

            try:
                # need to set the colors, sometimes color tables are not copied
                # flag w will end in error if there is already table
                env = self.env.copy()
                env['GRASS_MESSAGE_FORMAT'] = 'silent'
                gscript.run_command('r.colors', map=name, quiet=True, rules=rules, flags='w', env=env)
            except CalledModuleError:
                pass
            self.ShowTreatmentReplay(name, self.currentCheckpoint)
            cmd = ['d.rast', 'values=0', 'flags=i', 'map={}'.format(name)]
            opacity = float(self.params.pops['results_opacity']) if 'results_opacity' in self.params.pops else 1
            self._changeResultsLayer(cmd=cmd, name=name, opacity=opacity, resultType='results', useEvent=False)

    def ShowBaseline(self):
        # change layers
        displayTime = self.checkpoints[self.currentCheckpoint]
        event = self.getEventName()
        name = self.params.baseline['probability_series'] + '__' + event + '__'
        suffix = "{y}_{m:02d}_{d:02d}".format(y=displayTime[0], m=displayTime[1], d=displayTime[2])

        rules = os.path.join(self.workdir, self.params.pops['color_probability'])
        name = name + suffix

        if self.currentCheckpoint == 0:
            self.ShowInitalInfection(useEvent=False, show=True)
        else:
            self.ShowInitalInfection(useEvent=False, show=False)

        f = gscript.find_file(name=name, element='raster')
        if not f['fullname']:
            # display empty raster
            self._changeResultsLayer(cmd=['d.rast', 'map=' + self.empty_placeholders['results']],
                                     name=self.empty_placeholders['results'], resultType='results', useEvent=False)
        else:
            try:
                # need to set the colors, sometimes color tables are not copied
                # flag w will end in error if there is already table
                env = self.env.copy()
                env['GRASS_MESSAGE_FORMAT'] = 'silent'
                gscript.run_command('r.colors', map=name, quiet=True, rules=rules, flags='w', env=env)
            except CalledModuleError:
                pass
            cmd = ['d.rast', 'values=0', 'flags=i', 'map={}'.format(name)]
            opacity = float(self.params.pops['results_opacity']) if 'results_opacity' in self.params.pops else 1
            self._changeResultsLayer(cmd=cmd, name=name, opacity=opacity, resultType='results', useEvent=False)

    def ShowResults(self):
        # change layers
        self.ShowTreatment()
        displayTime = self.checkpoints[self.currentCheckpoint]
        event = self.getEventName()
        attempt = self.attempt.getCurrentFormatted(delim='_')
        name = self._createPlayerName()
        prefix = "{e}__{n}__{a}__".format(n=name, e=event, a=attempt)
        prefix_prob = self.configuration['POPS']['model']['probability_series'] + '__' + prefix
        suffix = "{y}_{m:02d}_{d:02d}".format(y=displayTime[0], m=displayTime[1], d=displayTime[2])

        if self._ifShowProbability():
            rules = os.path.join(self.workdir, self.configuration['POPS']['color_probability'])
            name = prefix_prob + suffix
        else:
            rules = os.path.join(self.workdir, self.configuration['POPS']['color_trees'])
            name = prefix + suffix

        if self.currentRealityCheckpoint == 0:
            name = ''

        if self.currentCheckpoint == 0:
            self.ShowInitalInfection(useEvent=False, show=True)
        else:
            self.ShowInitalInfection(useEvent=False, show=False)

        f = gscript.find_file(name=name, element='raster')
        if not f['fullname']:
            # display empty raster
            self._changeResultsLayer(cmd=['d.rast', 'map=' + self.empty_placeholders['results']],
                                     name=self.empty_placeholders['results'], resultType='results', useEvent=False)
        else:
            try:
                # need to set the colors, sometimes color tables are not copied
                # flag w will end in error if there is already table
                env = self.env.copy()
                env['GRASS_MESSAGE_FORMAT'] = 'silent'
                gscript.run_command('r.colors', map=name, quiet=True, rules=rules, flags='w', env=env)
            except CalledModuleError:
                pass
            cmd = ['d.rast', 'values=0', 'flags=i', 'map={}'.format(name)]
            opacity = float(self.params.pops['results_opacity']) if 'results_opacity' in self.params.pops else 1
            self._changeResultsLayer(cmd=cmd, name=name, opacity=opacity, resultType='results', useEvent=False)

    def ShowTreatment(self):
        event = self.getEventName()
        attempt = str(self.attempt.getCurrent()[0])
        name = self._createPlayerName()
        name = '__'.join([self.configuration['POPS']['treatments'], event, name, attempt])
        style = {'fill_color': 'none', 'width': 2, 'label_color': 'white',
                 'label_size': 22, 'font': 'n019044l'}
        if 'treatments_vstyle' in self.configuration['POPS']:
            style.update(self.configuration['POPS']['treatments_vstyle'])
        style = [key + '=' + str(style[key]) for key in style]
        cmd = ['d.vect', 'map={}'.format(name), 'display=shape,cat', 'xref=center', 'yref=bottom'] + style

        self._changeResultsLayer(cmd=cmd, name=name, resultType='treatments', useEvent=False)


    def ShowTreatmentReplay(self, name, checkpoint):
        parts = name.split('__')
        if len(parts) >= 5:
            parts = parts[-4:]
        event, player, attempt, date = parts

        name = '__'.join([self.configuration['POPS']['treatments'], event, player, attempt.split('_')[0]])

        style = {'fill_color': 'none', 'width': 2, 'label_color': 'white',
                 'label_size': 22, 'font': 'n019044l'}
        if 'treatments_vstyle' in self.configuration['POPS']:
            style.update(self.configuration['POPS']['treatments_vstyle'])
        style = [key + '=' + str(style[key]) for key in style]

        start = dateFromString(self.params.model['start_date']).year
        cats = [str(year) for year in range(start, start + checkpoint)]
        selection = ['cats=' + ','.join(cats)]
        cmd = ['d.vect', 'map={}'.format(name), 'display=shape,cat', 'xref=center', 'yref=bottom'] + style + selection

        self._changeResultsLayer(cmd=cmd, name=name, resultType='treatments', useEvent=False)

    def RunBaseline(self, event):
        host = self.params.baseline['host']
        if 'region' in self.params.pops:
            region = self.params.pops['region']
            extent = gscript.parse_command('g.region', flags='gu', region=region)
            region = {'n': extent['n'], 's': extent['s'], 'w': extent['w'], 'e': extent['e'], 'align': host}
        else:
            studyArea = self.configuration['tasks'][self.current]['base']
            extent = gscript.raster_info(studyArea)
            region = {'n': extent['north'], 's': extent['south'], 'w': extent['west'], 'e': extent['east'], 'align': host}

        probability = self.params.baseline['probability_series']
        postfix = self.getEventName() + '_'
        probability = probability + '__' + postfix

        region = '{n},{s},{w},{e},{align}'.format(**region)
        baseline_params = self.params.baseline.copy()
        baseline_params.update({'probability_series': probability})
        self.steeringClient.baseline_set_params(self.params.model_name,
                                                  baseline_params, self.params.model_flags, region)
        self.steeringClient.compute_baseline()
        self.infoBar.ShowMessage("Computing baseline...")


    def _RunSimulation(self, event=None):
        print('_runSimulation')
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
        # update params, dashboard
        if self.webDashboard:
            # get new run collection
            self.webDashboard.new_runcollection()
            self.params.update()

        playerName = self._createPlayerName()

        host = self.params.model['host']
        if 'region' in self.params.pops:
            region = self.params.pops['region']
            extent = gscript.parse_command('g.region', flags='gu', region=region)
            region = {'n': extent['n'], 's': extent['s'], 'w': extent['w'], 'e': extent['e'], 'align': host}
        else:
            studyArea = self.configuration['tasks'][self.current]['base']
            extent = gscript.raster_info(studyArea)
            region = {'n': extent['north'], 's': extent['south'], 'w': extent['west'], 'e': extent['east'], 'align': host}

        probability = self.params.model['probability_series']
        average = self.params.model['average_series']
        postfix = self.getEventName() + '__' + playerName + '_'
        probability = probability + '__' + postfix
        average = average + '__' + postfix

        region = '{n},{s},{w},{e},{align}'.format(**region)
        model_params = self.params.model.copy()
        model_params.update({'single_series': postfix,
                             'probability_series': probability,
                             'average_series': average})

        # run simulation
        self.steeringClient.simulation_set_params(self.params.model_name,
                                                  model_params, self.params.model_flags, region)
        self.steeringClient.simulation_start(restart)

    def RunSimulation(self, event=None):
        if self.steeringClient.simulation_is_running():
            # if simulation in the beginning, increase major version and restart the simulation
            if self.currentCheckpoint == 0:
                self.RestartSimulation()
            else:
                self.attempt.increaseMinor()
        else:
            self.InitSimulation()

        if self.webDashboard:
            self.webDashboard.create_run()
        #self.showDisplayChange = False

        self.infoBar.ShowMessage("Running...")
        playerName = self._createPlayerName()
        new_attempt = self.attempt.getCurrent()

        # grab a new raster of conditions
        # process new input layer
        host = self.params.model['host']
        cost_per_meter_squared = self.params.pops['cost_per_meter_squared']

        if 'region' in self.params.pops:
            region = self.params.pops['region']
            env = get_environment(region=region, align=host)
        else:
            studyArea = self.configuration['tasks'][self.current]['base']
            env = get_environment(raster=studyArea, align=host)

        event = self.getEventName()
        # todo, save treatments
        if self.params.pops['steering']['move_current_year']:
            checkpoint = self.currentCheckpoint
        else:
            checkpoint = self.currentRealityCheckpoint
        tr_name = self.treatments.name_treatment(event, playerName, new_attempt, checkpoint)
        # create treatment vector of all used treatments in that scenario
        tr_vector = self.treatments.create_treatment_vector(tr_name, env=env)

        # measuring area
        self.treated_area = self.treatments.compute_treatment_area(tr_name)
        self.treatmentHistory[self.currentCheckpoint] = self.treated_area
        self.money_spent = self.treated_area * cost_per_meter_squared

        # compute proportion
        self.treatments.resample(tr_name)

        if self.steeringClient.is_steering():
            if self.params.pops['steering']['move_current_year']:
                tr_year = dateFromString(self.params.model['start_date']).year + self.currentCheckpoint
            else:
                tr_year = dateFromString(self.params.model['start_date']).year + self.currentRealityCheckpoint
        else:
            tr_year = dateFromString(self.params.model['start_date']).year

        if self.webDashboard:
            self.webDashboard.set_management(polygons=tr_vector, cost=self.money_spent,
                                             area=self.treated_area, year=tr_year)
            self.webDashboard.update_run()

        # export treatments file to server
        self.steeringClient.simulation_send_data(tr_name, tr_name, env)
        # load new data here
        tr_date = dateToString(dateFromString(self.params.pops['treatment_date']).replace(year=tr_year))
        self.steeringClient.simulation_load_data(tr_name, tr_date,
                                                 self.params.model['treatment_length'],
                                                 self.params.model['treatment_application'])
        if self.params.pops['steering']['move_current_year']:
            self.steeringClient.simulation_goto(self.currentCheckpoint)
        else:
            self.steeringClient.simulation_goto(self.currentRealityCheckpoint)

        if self.params.pops['steering']['move_current_year']:
            self.currentRealityCheckpoint = self.currentCheckpoint + 1
        else:
            self.currentCheckpoint = self.currentRealityCheckpoint
            self.currentRealityCheckpoint += 1

        if self.visualizationModes[self.visualizationMode] != 'probability':
            self.steeringClient.simulation_sync_runs()

        if self.steeringClient.is_steering():
            self._one_step = True
        else:
            self._one_step = None
        self.steeringClient.simulation_play()

        self.HideResultsLayers()
        self.ShowTreatment()

        self.treatments.reset_registered_treatment()

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
                if self.params.model['average_series'] in name:
                    continue
                if self.params.model['probability_series'] in name and isProb:
                    found = True
                    rules = os.path.join(self.workdir, self.configuration['POPS']['color_probability'])
                elif not (self.params.model['probability_series']  in name or isProb):
                    found = True
                    rules = os.path.join(self.workdir, self.configuration['POPS']['color_trees'])
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
                    currentCheckpoint = int(year) - dateFromString(self.params.model['start_date']).year + 1
                    self.checkpoints[currentCheckpoint] = (int(year), int(month), int(day))
                    # hide infection in case it's visible
                    self.ShowInitalInfection(useEvent=True, show=False)

                    # when steering, jump just one step but keep processing outputs
                    if self._one_step or self._one_step is None:
                        self.currentCheckpoint = currentCheckpoint
                        evt = updateTimeDisplay(current=self.currentRealityCheckpoint,
                                                currentView=self.currentCheckpoint,
                                                vtype=self.visualizationModes[self.visualizationMode])
                        self.scaniface.postEvent(self, evt)

                        opacity = float(self.params.pops['results_opacity']) if 'results_opacity' in self.params.pops else 1
                        self._changeResultsLayer(cmd=cmd, name=name, opacity=opacity, resultType='results', useEvent=True)
                        if self._one_step:
                            self._one_step = False
        event.Skip()

    def _reloadAnalysisFile(self, funcPrefix):
        analysesFile = os.path.join(self.workdir, self.configuration['tasks'][self.current]['analyses'])
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

    def _baselineDone(self, event):
        self.infoBar.Dismiss()


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
        self.params.UnInit()

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
        self.params.read_initial_params()
        self.treatments.set_model_settings(self.params)
        self._initVisualizationModes()

        self.currentCheckpoint = 0
        start = dateFromString(self.params.model['start_date']).year
        end = dateFromString(self.params.model['end_date']).year
        self.checkpoints.append((start, 1, 1))
        year = start
        while year <= end:
            self.checkpoints.append((year, 12, 31))
            year += 1

        self.showDisplayChange = True
        self.switchCurrentResult = 0
        self.scaniface.additionalParams4Analyses = {"pops": self.configuration['POPS'],
                                                    "zoom_name": self._zoomName}
        self.LoadLayers()
        self.AddTempLayers()
        if self.treatmentSelect.GetValue():
            self.ChangeRegion()

        event = self.getEventName()
        self.attempt.initialize(event, player=self._createPlayerName())

        self.settings['analyses']['file'] = os.path.join(self.workdir, self.configuration['tasks'][self.current]['analyses'])
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
        # time status display
        if 'time_status_display' in self.configuration['tasks'][self.current]:
            self.StartTimeStatusDisplay()
        # start display timer
        self.timer.Start(self.speed)
        # reset registered treatment
        self.treatments.reset_registered_treatment()

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
            if self.timeStatusDisplay:
                self.timeStatusDisplay.Destroy()
                self.timeStatusDisplay = None

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
        # if standalone, no binding can be done
        windows = [wx.GetTopLevelParent(self)]
        if not self.IsStandalone():
            windows.append(self.giface.lmgr)
            windows.extend([mapw for mapw in self.giface.GetAllMapDisplays()])
        bindings = {'simulate': self._RunSimulation, 'visualization': lambda evt: self.SwitchVizMode(),
                    'stepforward': self.StepForward, 'stepback': self.StepBack, 'reset': self.ResetSimulation,
                    'defaultzoom': self._onDefaultRegion, 'registertreatment': lambda evt: self.treatments.register_treatment()}
        if "keyboard_events" in self.configuration:
            items = []
            for key in self.configuration['keyboard_events']:
                eventName = self.configuration['keyboard_events'][key]
                eventId = wx.NewId()
                items.append((wx.ACCEL_NORMAL, int(key), eventId))
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
        self.steeringClient.results_clear()

        start = 0
        end = dateFromString(self.params.model['end_date']).year - dateFromString(self.params.model['start_date']).year + 1
        if forward and self.currentCheckpoint >= end:
            return
        if not forward and self.currentCheckpoint <= start:
            return
        self.currentCheckpoint = self.currentCheckpoint + 1 if forward else self.currentCheckpoint - 1
        if self.timeDisplay:
            self.timeDisplay.UpdateText(self.currentRealityCheckpoint, self.currentCheckpoint, self.visualizationModes[self.visualizationMode])
        if self.timeStatusDisplay:
            self.timeStatusDisplay.UpdateText(self.currentCheckpoint, "forecast" if self._ifShowProbability() else "occurrence")

        if self.replaySelect.GetValue():
            self.Replay(self.replaySelect.GetValue())
        elif self.currentRealityCheckpoint == 0:
            self.ShowBaseline()
        else:
            self.ShowResults()

    def _checkDynamicZoom(self, event):
        if not self.treatmentSelect.GetValue():
            res = gscript.find_file(name=self._zoomName, element='windows')
            if res and res['name']:
                self.scaniface.additionalParams4Analyses = {"pops": self.configuration['POPS'],
                                                            "zoom_name": None}
                self.treatmentSelect.SetValue(self._zoomName)
                self.ChangeRegion()

        event.Skip()

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
        gscript.run_command('g.remove', type='region', name=self._zoomName, flags='f')
        self.scaniface.additionalParams4Analyses = {"pops": self.configuration['POPS'],
                                                    "zoom_name": self._zoomName}
        self.ChangeRegion()

    def AddTempLayers(self):
        if self.IsStandalone():
            return
        # create empty placeholders
        f = gscript.find_file(name=self.placeholders['results'], element='raster')
        env = get_environment(raster=self.configuration['tasks'][self.current]['base'])
        if not f['fullname']:
            gscript.mapcalc(self.empty_placeholders['results'] + " = null()", env=env)

        f = gscript.find_file(name=self.placeholders['treatments'], element='vector')
        if not f['fullname']:
            gscript.run_command('v.edit', tool='create', map=self.empty_placeholders['treatments'], env=env)

        ll = self.giface.GetLayerList()
        ll.AddLayer('raster', name=self.empty_placeholders['results'],
                    cmd=['d.rast', 'map=' + self.empty_placeholders['results']], checked=True)
        ll.AddLayer('vector', name=self.empty_placeholders['treatments'],
                    cmd=['d.vect', 'map=' + self.empty_placeholders['treatments']], checked=True)

    def LoadLayers(self):
        if self.IsStandalone():
            return
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
        if self.IsStandalone():
            return
        base = self.configuration['tasks'][self.current]['base']
        self.giface.GetMapWindow().Map.GetRegion(rast=[base], update=True)
        self.giface.GetMapWindow().UpdateMap()

    def ZoomToRegion(self, region):
        if self.IsStandalone():
            return
        self.giface.GetMapWindow().Map.GetRegion(regionName=region, update=True)
        self.giface.GetMapWindow().UpdateMap()

    def _changeResultsLayer(self, cmd, name, resultType, useEvent, opacity=1):
        if self.IsStandalone():
            return
        ll = self.giface.GetLayerList()
        if not hasattr(ll, 'ChangeLayer'):
            print("Changing layer in Layer Manager requires GRASS GIS version > 7.8")
            return
        # TODO: check there is exactly one layer
        pl_layer = ll.GetLayersByName(self.placeholders[resultType])[0]

        if useEvent:
            evt = changeLayer(layer=pl_layer, cmd=cmd, opacity=opacity)
            self.scaniface.postEvent(self.scaniface, evt)
        else:
            ll.ChangeLayer(pl_layer, cmd=cmd, opacity=opacity)
        self.placeholders[resultType] = name

    def HideResultsLayers(self, useEvent=False):
        self._changeResultsLayer(cmd=['d.rast', 'map=' + self.empty_placeholders['results']],
                                 name=self.empty_placeholders['results'], resultType='results', useEvent=useEvent)
        self._changeResultsLayer(cmd=['d.vect', 'map=' + self.empty_placeholders['treatments']],
                                 name=self.empty_placeholders['treatments'], resultType='treatments', useEvent=useEvent)

    def ShowInitalInfection(self, useEvent, show=True):
        if self.IsStandalone():
            return
        # assumes initial infection is named the same way as infected raster
        infected = self.params.model['infected']
        ll = self.giface.GetLayerList()
        for l in ll:
            if l.maplayer.name:
                name = l.maplayer.name.split('@')[0]
                if name == infected and (show is not ll.IsLayerChecked(l)):
                    if useEvent:
                        evt = checkLayers(layers=[l], checked=show)
                        self.scaniface.postEvent(self.scaniface, evt)
                    else:
                        ll.CheckLayer(l, checked=show)
                    break

    def RemoveLayers(self, etype='raster', pattern=None, layers=None):
        if self.IsStandalone():
            return
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
        title = None if 'title' not in self.tasks[self.current]['display'] else self.tasks[self.current]['display']['title']
        vertical = False if 'vertical' not in self.tasks[self.current]['display'] else self.tasks[self.current]['display']['vertical']
        fontsize = self.tasks[self.current]['display']['fontsize']
        maximum = self.tasks[self.current]['display']['maximum']
        formatting_string = self.tasks[self.current]['display']['formatting_string']
        self.dashboardFrame = MultipleHTMLDashboardFrame(self, fontsize=fontsize, maximum=maximum,
                                                         title=title, formatting_string=formatting_string,
                                                         vertical=vertical, average=None)
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
        if self.IsStandalone():
            md = wx.GetTopLevelParent(self)
        else:
            md = self.giface.GetMapDisplay()
        mdSize = md.GetSize()
        mdPos = md.GetPosition()
        return (mdPos[0] + pos[0] * mdSize[0], mdPos[1] + pos[1] * mdSize[1])

    def _getSizeFromRelative(self, size):
        if self.IsStandalone():
            md = wx.GetTopLevelParent(self)
        else:
            md = self.giface.GetMapDisplay()
        mdSize = md.GetSize()
        return (size[0] * mdSize[0], size[1] * mdSize[1])

    def StartTimeDisplay(self):
        self.timeDisplay = SteeringDisplayFrame(self, start=dateFromString(self.params.model['start_date']).year,
                                       end=dateFromString(self.params.model['end_date']).year + 1,
                                       fontsize=self.configuration['tasks'][self.current]['time_display']['fontsize'],
                                       vtype=self.visualizationModes[self.visualizationMode],
                                       color_scheme=['red', 'green'])

        pos = self._getDashboardPosition(key='time_display')
        size = self._getDashboardSize(key='time_display')
        self.timeDisplay.SetSize(size)
        self.timeDisplay.Show()
        self.timeDisplay.SetPosition(pos)
        evt = updateTimeDisplay(current=self.currentRealityCheckpoint,
                                currentView=self.currentCheckpoint,
                                vtype=self.visualizationModes[self.visualizationMode])
        self.scaniface.postEvent(self, evt)

    def StartTimeStatusDisplay(self):
        self.timeStatusDisplay = CurrentViewDisplayFrame(self, start=dateFromString(self.params.model['start_date']).year,
                                       end=dateFromString(self.params.model['end_date']).year + 1,
                                       fontsize=self.configuration['tasks'][self.current]['time_status_display']['fontsize'],
                                       beginning_of_year=self.configuration['tasks'][self.current]['time_status_display']['beginning_of_year'],
                                       fgcolor=self.configuration['tasks'][self.current]['time_status_display'].get('fgcolor', None),
                                       bgcolor=self.configuration['tasks'][self.current]['time_status_display'].get('bgcolor', None))

        pos = self._getDashboardPosition(key='time_status_display')
        size = self._getDashboardSize(key='time_status_display')
        self.timeStatusDisplay.SetSize(size)
        self.timeStatusDisplay.Show()
        self.timeStatusDisplay.SetPosition(pos)
        evt = updateTimeDisplay(current=self.currentRealityCheckpoint,
                                currentView=self.currentCheckpoint,
                                vtype=self.visualizationModes[self.visualizationMode])
        self.scaniface.postEvent(self, evt)


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
