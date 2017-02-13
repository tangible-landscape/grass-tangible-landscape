# -*- coding: utf-8 -*-
"""
@brief experiment_drain

This program is free software under the GNU General Public License
(>=v2). Read the file COPYING that comes with GRASS for details.

@author: Anna Petrasova (akratoc@ncsu.edu)
"""
import os
from datetime import datetime
from math import sqrt
import analyses
from tangible_utils import get_environment
import grass.script as gscript



# needed layers PERMANENT:
# r elevation
# v target point
# v contours

# needed empty layers in scanning mapset:
# v drain
# v change

solution = [(316715, 251545),
            (317045, 251065),
            (317485, 252475),
            (316765, 250475),
            (317055, 250705),
            (315725, 251855),
            (317705, 252645)]

def run_drain(real_elev, scanned_elev, eventHandler, env, **kwargs):
    before = 'scan_saved'
    analyses.change_detection(before=before, after=scanned_elev,
                              change='change', height_threshold=[100, 220], cells_threshold=[5, 80], add=True, max_detected=1, debug=True, env=env)
    point = gscript.read_command('v.out.ascii', input='change',
                                 type='point', format='point', env=env).strip()
    drain = 'drain_line'
    env2 = get_environment(raster=real_elev)
    if point:
        x, y, cat = point.split('|')
        gscript.run_command('r.drain', input=real_elev, output=drain, drain=drain, start_coordinates='{},{}'.format(x, y), env=env2)
    else:
        gscript.run_command('v.edit', map=drain, tool='create', env=env)

    # copy results
    postfix = datetime.now().strftime('%H_%M_%S')
    prefix = 'drain'
    gscript.run_command('g.copy', vector=['change', '{}_change_{}'.format(prefix, postfix)], env=env)


def post_drain(real_elev, scanned_elev, filterResults, timeToFinish, subTask, logDir, env):
    gisenv = gscript.gisenv()
    logFile = os.path.join(logDir, 'log_{}_drain.csv'.format(gisenv['LOCATION_NAME']))
    scoreFile = os.path.join(logDir, 'score_{}.csv'.format(gisenv['LOCATION_NAME']))
    points = gscript.list_grouped(type='vector', pattern="*change_*_*_*", exclude="*processed")[gisenv['MAPSET']]
    times = [each.split('_')[-3:] for each in points]
    points_text = []
    mode = 'w' if subTask == 0 else 'a'
    with open(logFile, mode) as f:
        if subTask == 0:
            f.write('time,distance,subTask\n')
        distances = []
        for i in range(len(points)):
            px, py, pc = gscript.read_command('v.out.ascii', input=points[i], type='point', format='point', env=env).strip().split('|')
            px, py = float(px), float(py)
            points_text.append('{}|{}'.format(px, py))
            dist = sqrt((px - solution[subTask][0]) * (px - solution[subTask][0]) + (py - solution[subTask][1]) * (py - solution[subTask][1]))
            distances.append(dist)
            gscript.run_command('g.rename', vector=[points[i], points[i] + '_processed'], env=env)
            time = times[i]
            f.write('{time},{d},{sub}\n'.format(time='{}:{}:{}'.format(time[0], time[1], time[2]), d=dist, sub=subTask))


    with open(scoreFile, 'a') as f:
        # mean from last 3 slopes
        dist_score = sum(distances[-3:]) / 3.
        # here convert to some scale?
        f.write("drain distance: {}\n".format(dist_score))
        f.write("filtered scans: {}\n".format(filterResults))
        f.write("time: {}\n".format(timeToFinish))
