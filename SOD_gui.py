# -*- coding: utf-8 -*-
"""
Created on Fri Dec 18 16:00:49 2015

@author: Anna Petrasova
"""
import os
import sys
import wx
import subprocess

import grass.script as gscript
from grass.exceptions import CalledModuleError

from tangible_utils import get_environment, remove_temp_regions


SOD_PATH = '/home/gis/Development/SOD-modeling/'

import pandas as pd
import json

# Chart labels
titles = {"n_dead_oaks": "Number of Dead Oaks", 
          "percent_dead_oaks": "Percentage of Dead Oaks",
          "n_saved_oaks": "Number of Saved Oaks",
          "infected_area_ha": "Infected Area (ha)", 
          "money_spent": "Money Spent",
          "area_treated_ha": "Area Treated (ha)", 
          "price_per_oak": "Price per Oak"}

def precison(num_list, round_num):
    new_list = [round(num, round_num) for num in num_list]
    return new_list
    
def sodCsvToJson(csv_file_path, out_file_path):
    # Output JSON object
    results_json = {}
    scenarios = []
    # Pandas DataFrame - reading in CSV file. Unable to extract attributes by columns.
    df =pd.read_csv(csv_file_path)
    # Extract CSV header
    header =  df.columns.values.tolist()
    
    for h in header:
        if h != "scenario":
            results_json[h] = {"title": "", "value": ""}
   
    for name in header:
        if name == "scenario":
            scenarios = df[name].tolist()
        else:
            #print name, df[name].tolist()
            value = df[name].tolist()
            value_list = []
            if name == "percent_dead_oaks":
                value = precison(value, 3)
            if name == "price_per_oak":
                value = precison(value, 8)
            
            rj = results_json[name]
            rj["title"] = titles[name]
            
            for s in range(len(scenarios)):
                obj = {"scenario": scenarios[s], "Y": value[s]}
                value_list.append(obj);
            rj["value"] = value_list
            results_json[name] = rj
    
    # Write a JSON file
    with open(out_file_path, 'w') as outfile:
        json.dump(results_json, outfile, indent=4, sort_keys=True)
        
    print "CSV converted to JSON"


class SODPanel(wx.Panel):
    def __init__(self, parent, giface):
        wx.Panel.__init__(self, parent)
        self.giface = giface

        mainSizer = wx.BoxSizer(wx.VERTICAL)
        output_name = wx.TextCtrl(self, value="scen1")
        analysis = wx.Button(self, label = "Run")
        analysis.Bind(wx.EVT_BUTTON, lambda evt: self.RunSOD(output_name.GetValue()))

        sizer = wx.BoxSizer(wx.HORIZONTAL)
        sizer.Add(wx.StaticText(self, label="Output name:"), flag=wx.ALIGN_CENTER_VERTICAL)
        sizer.Add(output_name, proportion=1, flag=wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, border=5)
        sizer.Add(analysis, flag=wx.ALIGN_CENTER_VERTICAL)
        mainSizer.Add(sizer, flag=wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, border=5)

        self.SetSizer(mainSizer)
        mainSizer.Fit(self)
        
    def RunSOD(self, output_name):
        if not output_name:
            return
 
        UMCA = 'UMCA_den_100m'
        UMCA_changed = 'UMCA_changed'
        tmp_regions = []
        env = get_environment(tmp_regions, raster=UMCA)

        self.run_simulation(changed_input=UMCA_changed, output=output_name, env=env)
        metrics = self.compute_metrics(simulated_oaks=output_name + '_573', simulated_umca=output_name + 'umca_573', env=env)
        n_dead_oaks, perc_dead_oaks, n_saved_oaks, infected, money, area, price_per_oak = metrics
        path = '/home/gis/Desktop/disease_metrics/results_SOD.csv'
        path_out = '/home/gis/Development/dashboard/cgaoak/data/results.json'
        if not os.path.exists(path):
            with open(path, 'w') as f:
                f.write('scenario,n_dead_oaks,percent_dead_oaks,n_saved_oaks,infected_area_ha,money_spent,area_treated_ha,price_per_oak\n')
        with open(path, 'a+') as f:
            f.write('{scen},{ndead},{perc_dead:.3f},{saved},{inf_area},{money},{area},{price_per_oak}\n'.format(scen=output_name, ndead=n_dead_oaks,
                    perc_dead=perc_dead_oaks, saved=n_saved_oaks, inf_area=infected, money=money, area=area, price_per_oak=price_per_oak))

        remove_temp_regions(tmp_regions)

        for each in self.giface.GetAllMapDisplays():
             each.GetMapWindow().UpdateMap()
        sodCsvToJson(path, path_out)


    def run_simulation(self, changed_input, output, env):
        ########## hardcoded 
        os.chdir(SOD_PATH)
        subprocess.call(['Rscript', 'scripts/SOD_aniso_clim_RGRASS.r',
                         '--umca=' + changed_input, '--oaks=OAKS_den_100m', '--livetree=TPH_den_100m',
                         '--image=ortho_5m_color.tif', '--sources=init_2000_cnt', '--nth_output=4',
                         '--start=2000', '--end=2010', '--seasonal=YES', '--wind=YES', '--pwdir=NE', '--scenario=random', '--output=' + output], env=env) #

        gscript.run_command('t.create', output=output, title='title', description='descrition', env=env)
        maps = gscript.list_grouped('raster', pattern=output + "_*")[gscript.gisenv()['MAPSET']]
        gscript.run_command('t.register', input=output, maps=','.join(maps[1:]), env=env)
        gscript.run_command('t.rast.colors', input=output, rules='infection_colors.txt', env=env)


    def compute_metrics(self, simulated_oaks, simulated_umca, env):
        # number of dead oaks in the last year
        n_dead_oaks_end = gscript.parse_command('r.univar', flags='g',  map=simulated_oaks, env=env)['sum']
        # % of dead oaks in the last year
        oaks_sum_all = 888232
        perc_dead_oaks_end = float(n_dead_oaks_end) / oaks_sum_all * 100
        # infected land
        infected_cells = gscript.parse_command('r.univar', flags='g', map=simulated_umca, env=env)['n']
        treated = gscript.parse_command('r.univar', flags='g',  map='cost_treated', env=env)
        money, area = treated['sum'], treated['n']
        n_saved_oaks = 2772 - float(n_dead_oaks_end)
        price_per_oak = float(money) / n_saved_oaks
        if n_saved_oaks < 0:
            n_saved_oaks = 0
            price_per_oak = 0

        return n_dead_oaks_end, perc_dead_oaks_end, n_saved_oaks, infected_cells, money, area, price_per_oak
