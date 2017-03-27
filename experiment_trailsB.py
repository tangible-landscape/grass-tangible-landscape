# -*- coding: utf-8 -*-
"""
@brief experiment_trailsB

This program is free software under the GNU General Public License
(>=v2). Read the file COPYING that comes with GRASS for details.

@author: Anna Petrasova (akratoc@ncsu.edu)
"""
import os
from datetime import datetime
from math import sqrt
import analyses
from tangible_utils import get_environment
from experiment import updateProfile
import grass.script as gscript
from grass.pygrass.vector import VectorTopo
from TSP import solve_tsp_numpy


def dist(points, i, j):
    x2 = (points[i][0] - points[j][0]) * (points[i][0] - points[j][0])
    y2 = (points[i][1] - points[j][1]) * (points[i][1] - points[j][1])
    return sqrt(x2 + y2)


def run_trails(real_elev, scanned_elev, eventHandler, env, **kwargs):
    resulting = "trails2_slopedir"
    before = 'scan_saved'
    #env_crop = get_environment(raster=real_elev, n='n-100', s='s+100', e='e-100', w='w+100')
    analyses.change_detection(before=before, after=scanned_elev,
                              change='change', height_threshold=[60, 335], cells_threshold=[3, 100], add=True, max_detected=10, debug=True, env=env)
    points = {}
    # start and end
    data = gscript.read_command('v.out.ascii', input='trails2_points', type='point', format='point', env=env).strip()
    c1, c2 = data.splitlines()
    c1 = c1.split('|')
    c2 = c2.split('|')
    points[0] = (float(c1[0]), float(c1[1]))
    points[1] = (float(c2[0]), float(c2[1]))

    # detected points
    points_raw = gscript.read_command('v.out.ascii', input='change',
                                      type='point', format='point').strip().split()
    i = 2
    for point in points_raw:
        point = point.split('|')
        point = (float(point[0]), float(point[1]))
        points[i] = point
        i += 1
    length = len(points)
    if length == 2:
        gscript.mapcalc("{} = null()".format(resulting), env=env)
        event = updateProfile(points=[])
        eventHandler.postEvent(receiver=eventHandler.experiment_panel, event=event)
        return

    # distance matrix
    D = []
    for i in range(length):
        D.append([0] * length)
    for p1 in range(0, length - 1):
        for p2 in range(p1 + 1, length):
            d = dist(points, p1, p2)
            D[p1][p2] = d
            D[p2][p1] = d
    # 0 distance for start and end to make sure it's always connected
    D[0][1] = 0
    D[1][0] = 0

    # solve
    solution = solve_tsp_numpy(D, optim_steps=10)
    # rearange solutions to start in start point
    ind1 = solution.index(0)
    ind2 = solution.index(1)
    if ind2 > ind1:
        solution = solution[::-1]
    ind = solution.index(0)
    solution = solution[ind :] + solution[:ind ]

    # export line
    profile_points = []
    line = 'L {} 1\n'.format(len(solution))
    for i in solution:
        line += '{} {}\n'.format(points[i][0], points[i][1])
        profile_points.append(points[i])
    line += '1 1'
    gscript.write_command('v.in.ascii', input='-', stdin=line, output='line', format='standard', flags='n', env=env)

    env2 = get_environment(raster=before)
    # slope along line
    gscript.run_command('v.to.rast', input='line', type='line', output='line_dir', use='dir', env=env2)
    gscript.run_command('r.slope.aspect', elevation=before, slope='saved_slope', aspect='saved_aspect', env=env2)
    gscript.mapcalc("slope_dir = abs(atan(tan({slope}) * cos({aspect} - {line_dir})))".format(slope='saved_slope', aspect='saved_aspect',
                    line_dir='line_dir'), env=env2)
    # set new color table
    colors = ['0 green', '7 green', '7 yellow', '15 yellow', '15 red', '90 red']
    gscript.write_command('r.colors', map='slope_dir', rules='-', stdin='\n'.join(colors), env=env2)
    # increase thickness
    gscript.run_command('r.grow', input='slope_dir', radius=2.1, output=resulting, env=env2)

    # update profile
    event = updateProfile(points=profile_points)
    eventHandler.postEvent(receiver=eventHandler.experiment_panel, event=event)
    # copy results
    postfix = datetime.now().strftime('%H_%M_%S')
    prefix = 'trails2'
    gscript.run_command('g.copy', raster=['slope_dir', '{}_slope_dir_{}'.format(prefix, postfix)],
                        vector=['line', '{}_line_{}'.format(prefix, postfix)], env=env)


def post_trails(real_elev, scanned_elev, filterResults, timeToFinish, logDir, env, **kwargs):
    env2 = get_environment(raster='scan_saved')
    gisenv = gscript.gisenv()
    logFile = os.path.join(logDir, 'log_{}_trails2.csv'.format(gisenv['LOCATION_NAME']))
    scoreFile = os.path.join(logDir, 'score_{}.csv'.format(gisenv['LOCATION_NAME']))
    slopes = gscript.list_grouped(type='raster', pattern="trails2_slope_dir_*_*_*")[gisenv['MAPSET']]
    lines = gscript.list_grouped(type='vector', pattern="trails2_line_*_*_*")[gisenv['MAPSET']]
    times = [each.split('_')[-3:] for each in slopes]
    score_sum = []
    score_max = []
    score_length = []
    score_points = []
    with open(logFile, 'w') as f:
        f.write('time,slope_min,slope_max,slope_mean,slope_sum,length,point_count\n')
        for i in range(len(slopes)):
            data_slopes = gscript.parse_command('r.univar', map=slopes[i], flags='g', env=env2)
            score_sum.append(float(data_slopes['sum']))
            score_max.append(float(data_slopes['max']))
            with VectorTopo(lines[i], mode='r') as v:
                try:
                    line = v.read(1)
                    point_count = len(line)
                    length = line.length()
                except IndexError:
                    length = 0
                    point_count = 0
                score_points.append(point_count)
                score_length.append(length)
            time = times[i]
            f.write('{time},{sl_min},{sl_max},{sl_mean},{sl_sum},{length},{cnt}\n'.format(time='{}:{}:{}'.format(time[0], time[1], time[2]),
                    sl_min=data_slopes['min'],
                    sl_max=data_slopes['max'],
                    sl_mean=data_slopes['mean'],
                    sl_sum=data_slopes['sum'],
                    length=length, cnt=point_count))
    with open(scoreFile, 'a') as f:
        # to make sure we don't get error if they skip quickly
        count = 3
        if len(score_points) < count:
            # shouldn't happen
            count = len(score_points)
        score_points = score_points[-count:]
        num_points = max(score_points)
        idx = score_points.index(num_points)
        slsum_score = score_sum[-count:][idx]
        slmax_score = score_max[-count:][idx]
        length_score = score_length[-count:][idx]

        # here convert to some scale?
        f.write("trails 2: sum slope: {}\n".format(slsum_score))
        f.write("trails 2: max slope: {}\n".format(slmax_score))
        f.write("trails 2: length line: {}\n".format(length_score))
        f.write("trails 2: filtered scans: {}\n".format(filterResults))
        f.write("trails 2: time: {}\n".format(timeToFinish))
