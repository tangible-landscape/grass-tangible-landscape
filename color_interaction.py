# -*- coding: utf-8 -*-
"""
@brief color_interaction

This program is free software under the GNU General Public License
(>=v2). Read the file COPYING that comes with GRASS for details.

@author: Anna Petrasova (akratoc@ncsu.edu)
"""
import wx

from gui_core.gselect import Select
import grass.script as gscript
from grass.pydispatch.signal import Signal
from grass.exceptions import CalledModuleError

from tangible_utils import get_environment


class ColorInteractionPanel(wx.Panel):
    def __init__(self, parent, giface, settings, scaniface):
        wx.Panel.__init__(self, parent)
        self.group = None
        self.segment = 'segment'
        self.segment_clump = 'segment_clump'
        self.signature = 'signature'
        self.classification = 'classification'
        self.filtered_classification = 'fclassification'
        self.reject = 'reject'
        self.output = 'objects'

        self.hasSuperpixels = gscript.find_program('i.superpixels.slic', '--help')

        self.env = None
        self.giface = giface
        self.parent = parent
        self.settings = settings
        self.scaniface = scaniface
        self.settingsChanged = Signal('ColorInteractionPanel.settingsChanged')

        if 'color' not in self.settings:
            self.settings['color'] = {}
            self.settings['color']['active'] = False
            self.settings['color']['name'] = ''
            self.settings['color']['training'] = ''

        self.hide = []
        self.ifColor = wx.CheckBox(self, label=_("Save color rasters:"))
        self.ifColor.SetValue(self.settings['color']['active'])
        self.ifColor.Bind(wx.EVT_CHECKBOX, self.OnChange)
        self.exportColor = Select(self, size=(-1, -1), type='raster')
        self.exportColor.SetValue(self.settings['color']['name'])
        self.exportColor.Bind(wx.EVT_TEXT, self.OnChange)
        self.hide.append(self.exportColor)
        if self.settings['color']['name']:
            self.group = self.settings['color']['name']

        self.trainingAreas = Select(self, size=(-1, -1), type='raster')
        self.trainingAreas.SetValue(self.settings['color']['training'])
        self.trainingAreas.Bind(wx.EVT_TEXT, self.OnChange)
        labelTraining = wx.StaticText(self, label=_("Training areas:"))
        self.hide.append(self.trainingAreas)
        self.hide.append(labelTraining)
        calibrateBtn = wx.Button(self, label=_("Calibrate"))
        calibrateBtn.Bind(wx.EVT_BUTTON, self.OnCalibration)
        self.hide.append(calibrateBtn)

        analyzeBtn = wx.Button(self, label=_("Scan and process"))
        analyzeBtn.Bind(wx.EVT_BUTTON, self.OnAnalysis)
        self.hide.append(analyzeBtn)

        self.mainSizer = wx.BoxSizer(wx.VERTICAL)
        sizer = wx.BoxSizer(wx.HORIZONTAL)
        sizer.Add(self.ifColor, flag=wx.ALIGN_CENTER_VERTICAL, border=5)
        sizer.Add(self.exportColor, proportion=1, flag=wx.ALIGN_CENTER_VERTICAL, border=5)
        self.mainSizer.Add(sizer, flag=wx.EXPAND | wx.ALL, border=5)
        sizer = wx.BoxSizer(wx.HORIZONTAL)
        sizer.Add(labelTraining, flag=wx.ALIGN_CENTER_VERTICAL, border=5)
        sizer.Add(self.trainingAreas, proportion=1, flag=wx.ALIGN_CENTER_VERTICAL, border=5)
        sizer.Add(calibrateBtn, flag=wx.ALIGN_CENTER_VERTICAL, border=5)
        self.mainSizer.Add(sizer, flag=wx.EXPAND | wx.ALL, border=5)
        sizer = wx.BoxSizer(wx.HORIZONTAL)
        sizer.AddStretchSpacer()
        sizer.Add(analyzeBtn, flag=wx.ALIGN_CENTER_VERTICAL, border=5)
        self.mainSizer.Add(sizer, flag=wx.EXPAND | wx.ALL, border=5)
        self.SetSizer(self.mainSizer)
        self.mainSizer.Fit(self)

        self._enable()

    def OnChange(self, event):
        self.settings['color']['training'] = self.trainingAreas.GetValue()
        self.settings['color']['active'] = self.ifColor.IsChecked()
        self.settings['color']['name'] = self.exportColor.GetValue()
        self.group = self.settings['color']['name']
        self._enable()

    def _enable(self):
        for each in self.hide:
            each.Enable(self.ifColor.IsChecked())

    def _defineEnvironment(self):
        try:
            gscript.read_command('i.group', flags='g', group=self.group, subgroup=self.group, env=self.env)
        except CalledModuleError:
            gscript.run_command('i.group', group=self.group, subgroup=self.group,
                                input=[self.group + '_' + ext for ext in 'r', 'g', 'b'], env=self.env)
        maps = gscript.read_command('i.group', flags='g', group=self.group, subgroup=self.group).strip()
        if maps:
            self.env = get_environment(raster=maps.splitlines()[0])

    def OnAnalysis(self, event):
        self._defineEnvironment()
        self.Run(self.Analyze)

    def OnCalibration(self, event):
        self._defineEnvironment()
        training = self.trainingAreas.GetValue()
        if not training:
            return
        self.Run(self.Calibrate)

    def Run(self, func):
        ll = self.giface.GetLayerList()
        checked = []
        for l in ll:
            if ll.IsLayerChecked(l):
                checked.append(l.cmd)
                ll.CheckLayer(l, False)
        wx.Yield()

        if not self.scaniface.IsScanning():
            self.scaniface.Scan(continuous=False)
            self.scaniface.process.wait()
            self.scaniface.process = None
            self.scaniface.status.SetLabel("Done.")
            self.Done(func, checked)
        elif self.scaniface.pause:
            pass
        else:
            wx.CallLater(3000, self.Done, func, checked)

    def Done(self, func, checked):
        func()
        ll = self.giface.GetLayerList()
        for l in ll:
            if l.cmd in checked:
                ll.CheckLayer(l, True)

    def Calibrate(self):
        gscript.run_command('i.gensigset', trainingmap=self.settings['color']['training'], group=self.group,
                            subgroup=self.group, signaturefile=self.signature, env=self.env, overwrite=True)  # we need here overwrite=True

    def Analyze(self):
        if self.hasSuperpixels:
            gscript.run_command('i.superpixels.slic', group=self.group, output=self.segment, compactness=2,
                                minsize=50, env=self.env)
        else:
            gscript.run_command('i.segment', group=self.group, output=self.segment, threshold=0.3, minsize=50, env=self.env)
            gscript.run_command('r.clump', input=self.segment, output=self.segment_clump, env=self.env)

        gscript.run_command('i.smap', group=self.group, subgroup=self.group, signaturefile=self.signature,
                            output=self.classification, goodness=self.reject, env=self.env)
        percentile = float(gscript.parse_command('r.univar', flags='ge', map=self.reject, env=self.env)['percentile_90'])
        gscript.mapcalc('{new} = if({classif} < {thres}, {classif}, null())'.format(new=self.filtered_classification,
                                                                                    classif=self.classification, thres=percentile), env=self.env)
        segments = self.segment if self.hasSuperpixels else self.segment_clump
        gscript.run_command('r.stats.quantile', base=segments, cover=self.filtered_classification, output=self.output, env=self.env)
