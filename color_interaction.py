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

from tangible_utils import get_environment, run_analyses, updateGUIEvt, EVT_UPDATE_GUI


class ColorInteractionPanel(wx.Panel):
    def __init__(self, parent, giface, settings):
        wx.Panel.__init__(self, parent)
        self.group = 'color'
        self.segment = 'segment'
        self.segment_clump = 'segment_clump'
        self.signature = 'signature'
        self.classification = 'classification'
        self.filtered_classification = 'fclassification'
        self.reject = 'reject'
        self.output = 'objects'

        self.env = None
        self.giface = giface
        self.settings = settings
        self.settingsChanged = Signal('ColorInteractionPanel.settingsChanged')

#        if 'drawing' not in self.settings:
#            self.settings['drawing'] = {}
#            self.settings['drawing']['active'] = False
#            self.settings['drawing']['name'] = ''
#            self.settings['drawing']['type'] = 'point'
#            self.settings['drawing']['append'] = False
#            self.settings['drawing']['appendName'] = ''
#            self.settings['drawing']['threshold'] = 760

        mainSizer = wx.BoxSizer(wx.VERTICAL)
        self.trainingAreas = Select(self, size=(-1, -1), type='raster')
        self.calibrateBtn = wx.Button(self, label=_("Calibrate"))
        self.calibrateBtn.Bind(wx.EVT_BUTTON, lambda evt: self.Calibration(self.trainingAreas.GetValue()))
        
        self.analyzeBtn = wx.Button(self, label=_("Scan and process"))
        self.analyzeBtn.Bind(wx.EVT_BUTTON, self.OnRun)

#        self.ifDraw = wx.CheckBox(self, label=_("Draw vector:"))
#        self.ifDraw.SetValue(self.settings['drawing']['active'])
#        self.ifDraw.Bind(wx.EVT_CHECKBOX, self.OnDrawChange)
#        self.ifDraw.Bind(wx.EVT_CHECKBOX, self.OnEnableDrawing)
#        self.draw_vector = Select(self, size=(-1, -1), type='vector')
#        self.draw_vector.SetValue(self.settings['drawing']['name'])
#        self.draw_vector.Bind(wx.EVT_TEXT, self.OnDrawChange)
#        self.draw_type = wx.RadioBox(parent=self, label="Vector type", choices=['point', 'line', 'area'])
#        {'point': 0, 'line': 1, 'area': 2}[self.settings['drawing']['type']]
#        self.draw_type.SetSelection({'point': 0, 'line': 1, 'area': 2}[self.settings['drawing']['type']])
#        self.draw_type.Bind(wx.EVT_RADIOBOX, self.OnDrawChange)
#        self.threshold = wx.SpinCtrl(parent=self, min=0, max=765, initial=int(self.settings['drawing']['threshold']))
#        self.threshold.SetValue(int(self.settings['drawing']['threshold']))
#        self.threshold.Bind(wx.EVT_SPINCTRL, self.OnDrawChange)
#        self.append = wx.CheckBox(parent=self, label="Append vector")
#        self.append.SetValue(self.settings['drawing']['append'])
#        self.append.Bind(wx.EVT_CHECKBOX, self.OnDrawChange)
#        self.appendName = Select(self, size=(-1, -1), type='vector')
#        self.appendName.SetValue(self.settings['drawing']['appendName'])
#        self.appendName.Bind(wx.EVT_TEXT, self.OnDrawChange)


        sizer = wx.BoxSizer(wx.HORIZONTAL)
        sizer.Add(wx.StaticText(self, label=_("Training areas:")), flag=wx.ALIGN_CENTER_VERTICAL, border=5)
        sizer.Add(self.trainingAreas, proportion=1, flag=wx.ALIGN_CENTER_VERTICAL, border=5)
        sizer.Add(self.calibrateBtn, flag=wx.ALIGN_CENTER_VERTICAL, border=5)
        mainSizer.Add(sizer, flag=wx.EXPAND | wx.ALL, border=5)
        sizer = wx.BoxSizer(wx.HORIZONTAL)
        sizer.AddStretchSpacer()
        sizer.Add(self.analyzeBtn, flag=wx.ALIGN_CENTER_VERTICAL, border=5)
        mainSizer.Add(sizer, flag=wx.EXPAND | wx.ALL, border=5)
        self.SetSizer(mainSizer)
        mainSizer.Fit(self)
        
    def _defineEnvironment(self):
        maps = gscript.read_command('i.group', flags='g', group=self.group, subgroup=self.group).strip()
        if maps:
            print 'set'
            self.env = get_environment(raster=maps.splitlines()[0])
        
    def OnRun(self, event):
        self._defineEnvironment()
        self.Analyze(self.env)
        
    def Calibration(self, training):
        self._defineEnvironment()
        gscript.run_command('i.gensigset', trainingmap=training, group=self.group, subgroup=self.group, signaturefile=self.signature, env=self.env)
    
    def Analyze(self, env):
        gscript.run_command('i.segment', group=self.group, output=self.segment, threshold=0.6, minsize=100, env=env)
        gscript.run_command('r.clump', input=self.segment, output=self.segment_clump, env=env)
        gscript.run_command('i.smap', group=self.group, subgroup=self.group, signaturefile=self.signature,
                            output=self.classification, goodness=self.reject, env=env)
        percentile = float(gscript.parse_command('r.univar', flags='ge', map=self.reject, env=env)['percentile_90'])
        gscript.mapcalc('{new} = if({classif} < {thres}, {classif}, null())'.format(new=self.filtered_classification,
                                                                                    classif=self.classification, thres=percentile), env=env)
        gscript.run_command('r.stats.quantile', base=self.segment_clump, cover=self.filtered_classification, output=self.output, env=env)
        