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


solution = [(316715, 251545, 1134.5),
            (317045, 251065, 1166.9),
            (317485, 252475, 1005.0),
            (316765, 250475, 1271.5),
            (317055, 250705, 1189.9),
            (315725, 251855, 929.2),
            (317705, 252645, 940.2)]


def run_drain(real_elev, scanned_elev, eventHandler, env, subTask, **kwargs):
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
    if point:
        postfix = datetime.now().strftime('%H_%M_%S')
        prefix = 'drain'
        gscript.run_command('g.copy', vector=['change', '{}_change_{}_{}'.format(prefix, subTask, postfix)], env=env)


def post_drain(real_elev, scanned_elev, filterResults, timeToFinish, subTask, logDir, env):
    env2 = get_environment(raster=real_elev)
    gisenv = gscript.gisenv()
    logFile = os.path.join(logDir, 'log_{}_drain.csv'.format(gisenv['LOCATION_NAME']))
    scoreFile = os.path.join(logDir, 'score_{}.csv'.format(gisenv['LOCATION_NAME']))
    points = gscript.list_grouped(type='vector', pattern="*change_{}_*_*_*".format(subTask))[gisenv['MAPSET']]
    times = [each.split('_')[-3:] for each in points]
    points_text = []
    mode = 'w' if subTask == 0 else 'a'
    with open(logFile, mode) as f:
        if subTask == 0:
            f.write('time,distance,subTask\n')
        for i in range(len(points)):
            px, py, pc = gscript.read_command('v.out.ascii', input=points[i], type='point', format='point', env=env).strip().split('|')
            px, py = float(px), float(py)
            points_text.append('{}|{}'.format(px, py))
            dist = sqrt((px - solution[subTask][0]) * (px - solution[subTask][0]) + (py - solution[subTask][1]) * (py - solution[subTask][1]))
            z = gscript.read_command('r.what', map=real_elev, coordinates=(px, py), env=env2).strip().split('|')[-1]
            pz = float(z)
            height_diff = solution[subTask][2] - pz
            time = times[i]
            f.write('{time},{d},{hd},{sub}\n'.format(time='{}:{}:{}'.format(time[0], time[1], time[2]), d=dist, hd=height_diff, sub=subTask))

    with open(scoreFile, 'a') as f:
        # test whether point is inside buffered watershed
        found = False
        query = gscript.vector_what(map='drain_basins_buffered', coord=(px, py))
        for each in query:
            if each['Category'] == subTask + 1:
                found = True

        f.write("drain: inside watershed: {}\n".format(found))
        f.write("drain: horizontal distance: {}\n".format(dist))
        f.write("drain: vertical distance: {}\n".format(height_diff))
        f.write("drain: filtered scans: {}\n".format(filterResults))
        f.write("drain: time since start: {}\n".format(timeToFinish))
