# -*- coding: utf-8 -*-
"""
@brief experiment_trails

This program is free software under the GNU General Public License
(>=v2). Read the file COPYING that comes with GRASS for details.

@author: Anna Petrasova (akratoc@ncsu.edu)
"""
import os
from math import sqrt
from datetime import datetime
import analyses
from tangible_utils import get_environment
import grass.script as gscript
from grass.pygrass.vector import VectorTopo



def run_contours(real_elev, scanned_elev, eventHandler, env, **kwargs):
    gscript.run_command('r.contour', input=scanned_elev, output='flow_contours', step=20, flags='t', env=env)


def run_flow(real_elev, scanned_elev, eventHandler, env, **kwargs):
    gscript.run_command('r.slope.aspect', elevation=scanned_elev, dx='dx', dy='dy', env=env)
    gscript.run_command('r.sim.water', elevation=scanned_elev, dx='dx', dy='dy', rain_value=300,
                        depth='flow_flow', niterations=6, env=env)
    # copy scan
    postfix = datetime.now().strftime('%H_%M_%S')
    prefix = 'dams'
    gscript.run_command('g.copy', raster=[scanned_elev, '{}_scan_{}'.format(prefix, postfix)], env=env)

#def post_flow(real_elev, scanned_elev, filterResults, timeToFinish, logDir, env, **kwargs):
#    gscript.run_command('r.slope.aspect', elevation=scanned_elev, dx='dx', dy='dy', env=env)
#    gscript.run_command('r.sim.water', elevation=scanned_elev, dx='dx', dy='dy', rain_value=300,
#                        depth='flow_flow_final', niterations=180, hmax=0.25, halpha=8, env=env)
#    return
#    env2 = get_environment(raster=real_elev)
#    gisenv = gscript.gisenv()
#    logFile = os.path.join(logDir, 'log_{}_trails1a.csv'.format(gisenv['LOCATION_NAME']))
#    scoreFile = os.path.join(logDir, 'score_{}.csv'.format(gisenv['LOCATION_NAME']))
#    slopes = gscript.list_grouped(type='raster', pattern="*slope_dir_*_*_*")[gisenv['MAPSET']]
#    lines = gscript.list_grouped(type='vector', pattern="*line_*_*_*")[gisenv['MAPSET']]
#    times = [each.split('_')[-3:] for each in slopes]
#    score_slopes = []
#    with open(logFile, 'w') as f:
#        f.write('time,slope_min,slope_max,slope_mean,slope_sum,length,point_count\n')
#        for i in range(len(slopes)):
#            data_slopes = gscript.parse_command('r.univar', map=slopes[i], flags='g', env=env2)
#            score_slopes.append(float(data_slopes['mean']))
#            with VectorTopo(lines[i], mode='r') as v:
#                try:
#                    line = v.read(1)
#                    point_count = len(line)
#                    length = line.length()
#                except IndexError:
#                    length = 0
#                    point_count = 0
#            time = times[i]
#            f.write('{time},{sl_min},{sl_max},{sl_mean},{sl_sum},{length},{cnt}\n'.format(time='{}:{}:{}'.format(time[0], time[1], time[2]),
#                    sl_min=data_slopes['min'],
#                    sl_max=data_slopes['max'],
#                    sl_mean=data_slopes['mean'],
#                    sl_sum=data_slopes['sum'],
#                    length=length, cnt=point_count))
#    with open(scoreFile, 'a') as f:
#        # mean from last 3 slopes
#        slope_score = sum(score_slopes[-3:]) / 3.
#        # here convert to some scale?
#        f.write("mean slope: {}\n".format(slope_score))
#        f.write("filtered scans: {}\n".format(filterResults))
#        f.write("time: {}\n".format(timeToFinish))
