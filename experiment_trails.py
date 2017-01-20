# -*- coding: utf-8 -*-
"""
@brief experiment_trails

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


# needed layers PERMANENT:
# r elevation
# r slope
# r aspect
# v AB

# needed empty layers in scanning mapset:
# v line
# v change
# r slope_class_buffer



def run_trails(real_elev, scanned_elev, eventHandler, env, **kwargs):
    analyses.change_detection(before=real_elev, after=scanned_elev,
                              change='change', height_threshold=[90, 160], cells_threshold=[3, 40], add=True, max_detected=4, env=env)
    data = gscript.read_command('v.out.ascii', input='trails1_points', type='point', format='point', env=env).strip()

    c1, c2 = data.splitlines()
    c1 = c1.split('|')
    c2 = c2.split('|')
    points = {}
    point_conn = {}
    distances = {}
    point_cat = {}
    line = ''
    points[0] = (float(c1[0]), float(c1[1]))
    points[1] = (float(c2[0]), float(c2[1]))
    point_conn[0] = 1
    point_conn[1] = 1
    point_cat[0] = 98
    point_cat[1] = 99
    points_raw = gscript.read_command('v.out.ascii', input='change',
                                      type='point', format='point').strip().split()    
    i = 2
    for point in points_raw:
        point = point.split('|')
        point_cat[i] = point[2]
        point = (float(point[0]), float(point[1]))
        points[i] = point
        point_conn[i] = 0
        i += 1
    if len(points) < 2:
        return
    for i in range(len(points) - 1):
        for j in range(i + 1, len(points)):
            distances[(i, j)] = sqrt((points[i][0] - points[j][0]) * (points[i][0] - points[j][0]) +
                                     (points[i][1] - points[j][1]) * (points[i][1] - points[j][1]))
    ordered = sorted(distances.items(), key=lambda x: x[1])
    connections = []
    i = 0
    while ordered and len(connections) < len(points) - 1:
        i += 1
        if i > 50:
            break
        connection = ordered.pop(0)
        p, d = connection[0], connection[1]
        p1, p2 = p[0], p[1]
        if point_conn[p1] >= 2 or point_conn[p2] >= 2:
#            print 'vyrazeny: ' + str(point_cat[p1]) + ' ' + str(point_cat[p2])
            continue
        else:
            # TODO: check if we create a loop
            point_conn[p2] += 1
            point_conn[p1] += 1
#            print 'pridany: ' + str(point_cat[p1]) + ' ' + str(point_cat[p2])
            connections.append(connection)

    start = 0
    ordered_connections = []
    len_connections = len(connections)
    valid = False
    for i, (c, d) in enumerate(connections):
        # if the first point has no connection, it's invalid
        if c[0] == 0 or c[1] == 0:
            valid = True
    if not valid:
        return
    i = 0
    while len(ordered_connections) != len_connections:
        i += 1
        if i > 50:
            break
        for i, (c, d) in enumerate(connections):
            if c[0] == start:
                ordered_connections.append((c[0], c[1]))
                start = c[1]
                del connections[i]
                break
            elif c[1] == start:
                ordered_connections.append((c[1], c[0]))
                start = c[0]
                del connections[i]
                break

    profile_points = []
    line += 'L {} 1\n'.format(len(ordered_connections) + 1)
    for l in ordered_connections:
        line += '{x} {y}\n'.format(x=points[l[0]][0], y=points[l[0]][1])
        profile_points.append(points[l[0]])
    line += '{x} {y}\n'.format(x=points[l[1]][0], y=points[l[1]][1])
    profile_points.append(points[l[1]])
    line += '1 1\n\n'
    gscript.write_command('v.in.ascii', input='-', stdin=line, output='line', format='standard', flags='n', overwrite=True, env=env)
    env2 = get_environment(raster=real_elev)
    # slope along line
    gscript.run_command('v.to.rast', input='line', type='line', output='line_dir', use='dir', env=env2)
    gscript.mapcalc("slope_dir = abs(atan(tan({slope}) * cos({aspect} - {line_dir})))".format(slope='trails1_slope', aspect='trails1_aspect',
                    line_dir='line_dir'), env=env2)
    # reclassify using rules passed as a string to standard input
    # 0:2:1 means reclassify interval 0 to 2 percent of slope to category 1 
    rules = ['0:5:1', '5:8:2', '8:10:3', '10:15:4', '15:30:5', '30:*:6']
    gscript.write_command('r.recode', input='slope_dir', output='slope_class',
                          rules='-', stdin='\n'.join(rules), env=env2)
    # set new color table
    colors = ['1 255:255:204', '2 199:233:180', '3 127:205:187', '4 65:182:196', '5 044:127:184', '6 037:052:148']
    gscript.write_command('r.colors', map='slope_class', rules='-', stdin='\n'.join(colors), env=env2)
    # increase thickness
    resulting = "trails1_slopedir"
    gscript.run_command('r.grow', input='slope_class', radius=1.1, output=resulting, env=env2)

    # update profile
    event = updateProfile(points=profile_points)
    eventHandler.postEvent(receiver=eventHandler.experiment_panel, event=event)
    # copy results
    postfix = datetime.now().strftime('%H_%M_%S')
    prefix = 'trails1'
#    gscript.run_command('g.copy', raster=['slope_dir', '{}_slope_dir_{}'.format(prefix, postfix)],
#                        vector=['line', '{}_line_{}'.format(prefix, postfix)], env=env)


def post_trails(real_elev, scanned_elev, filterResults, timeToFinish, logDir, env, **kwargs):
    env2 = get_environment(raster=real_elev)
    gisenv = gscript.gisenv()
    logFile = os.path.join(logDir, 'log_{}_trails1a.csv'.format(gisenv['LOCATION_NAME']))
    scoreFile = os.path.join(logDir, 'score_{}.csv'.format(gisenv['LOCATION_NAME']))
    slopes = gscript.list_grouped(type='raster', pattern="*slope_dir_*_*_*")[gisenv['MAPSET']]
    lines = gscript.list_grouped(type='vector', pattern="*line_*_*_*")[gisenv['MAPSET']]
    times = [each.split('_')[-3:] for each in slopes]
    score_slopes = []
    with open(logFile, 'w') as f:
        f.write('time,slope_min,slope_max,slope_mean,slope_sum,length,point_count\n')
        for i in range(len(slopes)):
            data_slopes = gscript.parse_command('r.univar', map=slopes[i], flags='g', env=env2)
            score_slopes.append(float(data_slopes['mean']))
            with VectorTopo(lines[i], mode='r') as v:
                try:
                    line = v.read(1)
                    point_count = len(line)
                    length = line.length()
                except IndexError:
                    length = 0
                    point_count = 0
            time = times[i]
            f.write('{time},{sl_min},{sl_max},{sl_mean},{sl_sum},{length},{cnt}\n'.format(time='{}:{}:{}'.format(time[0], time[1], time[2]),
                    sl_min=data_slopes['min'],
                    sl_max=data_slopes['max'],
                    sl_mean=data_slopes['mean'],
                    sl_sum=data_slopes['sum'],
                    length=length, cnt=point_count))
    with open(scoreFile, 'a') as f:
        # mean from last 3 slopes
        slope_score = sum(score_slopes[-3:]) / 3.
        # here convert to some scale?
        f.write("mean slope: {}\n".format(slope_score))
        f.write("filtered scans: {}\n".format(filterResults))
        f.write("time: {}\n".format(timeToFinish))
