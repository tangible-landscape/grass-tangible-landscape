# -*- coding: utf-8 -*-
"""
Created on Fri Dec 18 16:00:49 2015

@author: Anna Petrasova
"""
import os
import sys
import wx
import random
import subprocess

sys.path.append(os.path.join(os.environ['GISBASE'], "etc", "gui", "wxpython"))
from gui_core.gselect import Select
import grass.script as gscript
from grass.exceptions import CalledModuleError

from tangible_utils import get_environment, remove_temp_regions

class TermitesPanel(wx.Panel):
    def __init__(self, parent, giface):
        wx.Panel.__init__(self, parent)
        self.giface = giface
        
        self.colonies = 'init_colonies'
        self.habitat_orig = 'unsuitable_habitat'
        self.habitat = 'habitat_changed'
        self.round = 1
        mainSizer = wx.BoxSizer(wx.VERTICAL)
        output_name = wx.TextCtrl(self, value="scen1")
        analysis_baseline = wx.Button(self, label = "Run baseline")
        analysis = wx.Button(self, label = "Run")
        perturb = wx.Button(self, label = "Randomize")
        self.colonies_select = Select(self, size=(-1, -1), type='vector')
        self.colonies_select.SetValue('init_colonies@PERMANENT')
        analysis_baseline.Bind(wx.EVT_BUTTON, lambda evt: self.RunTermites(output_name.GetValue(), self.colonies_select.GetValue(), self.habitat_orig, True))
        analysis.Bind(wx.EVT_BUTTON, lambda evt: self.RunTermites(output_name.GetValue(), self.colonies_select.GetValue(), self.habitat, False))
        perturb.Bind(wx.EVT_BUTTON, lambda evt: self.Randomize())
        
        sizer = wx.BoxSizer(wx.HORIZONTAL)
        sizer.Add(wx.StaticText(self, label="Colonies:"), flag=wx.ALIGN_CENTER_VERTICAL)
        sizer.Add(self.colonies_select, proportion=1, flag=wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, border=5)
        sizer.Add(perturb, flag=wx.EXPAND|wx.ALL, border = 5)
        mainSizer.Add(sizer, flag=wx.EXPAND | wx.ALL, border=5)
        
        sizer = wx.BoxSizer(wx.HORIZONTAL)
        sizer.Add(wx.StaticText(self, label="Output name:"), flag=wx.ALIGN_CENTER_VERTICAL)
        sizer.Add(output_name, proportion=1, flag=wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, border=5)
        sizer.Add(analysis_baseline, flag=wx.ALIGN_CENTER_VERTICAL)
        sizer.Add(analysis, flag=wx.ALIGN_CENTER_VERTICAL)
        mainSizer.Add(sizer, flag=wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, border=5)

        self.SetSizer(mainSizer)
        mainSizer.Fit(self)
        
    def RunTermites(self, output_name, colonies, habitat, baseline):
        func = 'model_termites'
        if not output_name:
            return

        if baseline:
            self.round = 1
        model_termites(habitat, colonies, output_name, self.round)
        for each in self.giface.GetAllMapDisplays():
             each.GetMapWindow().UpdateMap()
        self.round += 1
        
    def model_termites(habitat_changed, init_colonies, output, round):
        tmp_regions = []
        env = get_environment(tmp_regions, raster=habitat_changed)
        name = output.split('@')[0] + "_" + str(round)
        subprocess.call(['Rscript', '/home/gis/Development/termites/CA_iso.R',
                         '--habitat=' + habitat_changed, '--sources=' + init_colonies, '--image=ortho.tiff', '--start=2003', '--end=2040',
                         '--tab=NewCol_table.csv', '--ktype=gauss', '--surv=0.01', '--maxd=10', '--kdist=100', '--output=' + name], env=env)
        gscript.run_command('t.create', output=name, title='title', description='descrition', env=env)
        maps = gscript.list_grouped('raster', pattern=name + "_*")[gscript.gisenv()['MAPSET']]
        #gscript.run_command('t.register', input=name, maps=','.join(maps[1:]), env=env)
        #gscript.run_command('t.rast.colors', input=name, rules='/home/gis/Development/termites/infection_colors.txt', env=env)
        #last = gscript.read_command('t.rast.list',  input=name, columns='name', method='comma', env=env).strip().split(',')[-1]
        last = maps[-1]
        gscript.run_command('r.colors', map=','.join(maps[1:]), rules='/home/gis/Development/termites/infection_colors.txt', env=env)
        gscript.run_command('g.copy', raster=[last, 'result'], env=env)
        area = float(gscript.parse_command('r.univar', map=last, flags='g', env=env)['n'])
        treatment_area = int(gscript.parse_command('r.univar', map=habitat_changed, flags='g', env=env)['n']) - 396
        before = ''
        if round > 1:
            before = gscript.read_command('v.db.select', flags='c', map='score', columns='area', env=env).strip() + "   "
        gscript.run_command('v.db.update', map='score', layer=1, column='area', value=before + str(round) + ': ' + str(int(area)), env=env)
        
        # save results
        if round == 1:
            gscript.run_command('g.copy', vector=[init_colonies.split('@')[0], init_colonies.split('@')[0] + output.split('@')[0]], env=env)
        if round > 1:
            gscript.run_command('g.copy', raster=[habitat_changed.split('@')[0], habitat_changed.split('@')[0] + name], env=env)
        path = '/home/gis/Desktop/results.csv'
        if not os.path.exists(path):
            with open(path, 'w') as f:
                pass
        with open(path, 'a') as f:
            f.write(name + ',' + str(area) + ',' + str(treatment_area) + '\n')
        remove_temp_regions(tmp_regions)

    def Randomize(self):
        out = 'init_colonies'
        gscript.run_command('v.perturb', input='init_colonies@PERMANENT',
                            output=out, distribution='normal',
                            parameters='0,100', seed=random.randint(1, 1e6), overwrite=True, quiet=True)
        self.colonies_select.SetValue(out)
