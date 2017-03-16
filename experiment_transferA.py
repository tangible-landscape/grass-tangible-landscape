# -*- coding: utf-8 -*-
"""
@brief experiment_transferA

This program is free software under the GNU General Public License
(>=v2). Read the file COPYING that comes with GRASS for details.

@author: Anna Petrasova (akratoc@ncsu.edu)
"""
import os
from datetime import datetime
import analyses
from tangible_utils import get_environment
from experiment import updateDisplay
import grass.script as gscript


def run_road(real_elev, scanned_elev, eventHandler, env, **kwargs):
    env2 = get_environment(raster=real_elev)
    before = 'scan_saved'
    analyses.change_detection(before=before, after=scanned_elev,
                              change='change', height_threshold=[18, 50], cells_threshold=[3, 100], add=True, max_detected=1, debug=True, env=env)
    point = gscript.read_command('v.out.ascii', input='change',
                                 type='point', format='point', env=env).strip()

    conn = 'transfer_connection'
    drain = 'transfer_drain'
    resulting = "transfer_slopedir"
    if point:
        x, y, cat = point.split('|')
        gscript.run_command('r.drain', input='transfer_cost', direction='transfer_costdir', output=conn,
                            start_points='change', drain=conn, flags='d', env=env2)

        gscript.run_command('v.to.rast', input=conn, type='line', output=conn + '_dir', use='dir', env=env2)
        gscript.mapcalc("slope_dir = abs(atan(tan({slope}) * cos({aspect} - {line_dir})))".format(slope='transfer_slope',
                        aspect='transfer_aspect', line_dir=conn + '_dir'), env=env2)
        # set new color table
        colors = ['0 green', '5 green', '5 yellow', '12 yellow', '12 red', '90 red']
        gscript.write_command('r.colors', map='slope_dir', rules='-', stdin='\n'.join(colors), env=env2)
        # increase thickness

        gscript.run_command('r.grow', input='slope_dir', radius=1.8, output=resulting, env=env2)

        # drain
        gscript.run_command('r.drain', input=real_elev, output=drain,
                            start_points='change', drain=drain, env=env2)

        gscript.run_command('r.viewshed', input=real_elev, output='transfer_viewshed', observer_elevation=67,
                            coordinates=[x, y], flags='b', env=env2)
        gscript.write_command('r.colors', map='transfer_viewshed', rules='-', stdin='0 black', env=env2)

        env3 = get_environment(raster='transfer_road')
        gscript.mapcalc('visible_road = if(transfer_viewshed == 1 && ! isnull(transfer_road), 1, null())', env=env3)
        #road_full = float(gscript.parse_command('r.univar', map='transfer_road', flags='g', env=env3)['n'])
        road_full = 500  # number of road cells
        try:
            road_v = float(gscript.parse_command('r.univar', map='visible_road', flags='g', env=env3)['n'])
        except KeyError:
            road_v = 0
        event = updateDisplay(value=int(100 * road_v / road_full))
    else:
        gscript.run_command('v.edit', map=conn, tool='create', env=env)
        gscript.run_command('v.edit', map=drain, tool='create', env=env)
        gscript.mapcalc('{} = null()'.format(resulting), env=env)
        gscript.mapcalc('{} = null()'.format('transfer_viewshed'), env=env)
        event = updateDisplay(value=None)

    # update viewshed score
    eventHandler.postEvent(receiver=eventHandler.experiment_panel, event=event)

    # copy results
    if point:
        postfix = datetime.now().strftime('%H_%M_%S')
        prefix = 'transfer1'
        gscript.run_command('g.copy', vector=['change', '{}_change_{}'.format(prefix, postfix)],
                            raster=['visible_road', '{}_visible_road_{}'.format(prefix, postfix)], env=env)
        gscript.run_command('g.copy', raster=['slope_dir', '{}_slope_dir_{}'.format(prefix, postfix)], env=env)


def post_transfer(real_elev, scanned_elev, filterResults, timeToFinish, subTask, logDir, env):
    gisenv = gscript.gisenv()
    logFile = os.path.join(logDir, 'log_{}_transfer1.csv'.format(gisenv['LOCATION_NAME']))
    scoreFile = os.path.join(logDir, 'score_{}.csv'.format(gisenv['LOCATION_NAME']))

    slopes = gscript.list_grouped(type='raster', pattern="transfer1_slope_dir_*_*_*")[gisenv['MAPSET']]
    roads = gscript.list_grouped(type='raster', pattern="transfer1_visible_road_*_*_*")[gisenv['MAPSET']]
    points = gscript.list_grouped(type='vector', pattern="transfer1_change_*_*_*")[gisenv['MAPSET']]
    times = [each.split('_')[-3:] for each in slopes]
    visible_road = []
    outside_of_buffer = []
    inbasin = []
    slope_sum = []
    slope_mean = []
    slope_max = []
    road_length = []

    with open(logFile, 'w') as f:
        f.write('time,visible_road,outside_buffer,inside_basin,slope_mean,slope_sum,slope_max,road_length\n')
        for i in range(len(slopes)):
            # visible road
            env2 = get_environment(raster=roads[i])
            try:
                road_v = float(gscript.parse_command('r.univar', map=roads[i], flags='g', env=env2)['n'])
            except KeyError:
                road_v = 0
            v_road_perc = road_v / 500.0
            visible_road.append(v_road_perc)
            # outside of buffer
            px, py, pc = gscript.read_command('v.out.ascii', input=points[i], type='point', format='point', env=env).strip().split('|')
            px, py = float(px), float(py)
            query = gscript.vector_what(map='transfer_streams_buffer', coord=(px, py))
            found = False
            print query
            for each in query:
                if 'Category' in each:
                    found = True
            outside_of_buffer.append(not found)
            # slope
            env3 = get_environment(raster=slopes[i])
            data_slopes = gscript.parse_command('r.univar', map=slopes[i], flags='g', env=env3)
            slope_sum.append(float(data_slopes['sum']))
            slope_mean.append(float(data_slopes['mean']))
            slope_max.append(float(data_slopes['max']))
            # approx length of road
            rinfo = gscript.raster_info(slopes[i])
            length = float(data_slopes['n']) * ((rinfo['nsres'] + rinfo['ewres']) / 2.)
            road_length.append(length)
            # basin
            query = gscript.vector_what(map='transfer_basin_buffered', coord=(px, py))
            found2 = False
            for each in query:
                if 'Category' in each:
                    found2 = True
            inbasin.append(found2)
            # time
            time = times[i]
            f.write('{time},{v_road},{outside_of_buffer},{inbasin},{sl_mean},{sl_sum},{sl_max},{length}\n'.format(time='{}:{}:{}'.format(time[0], time[1], time[2]),
                    v_road=v_road_perc,
                    outside_of_buffer=(not found),
                    inbasin=found2,
                    sl_mean=data_slopes['mean'],
                    sl_sum=data_slopes['sum'],
                    sl_max=data_slopes['max'],
                    length=length))


    with open(scoreFile, 'a') as f:
        # take means?
        if len(points) == 0:
            f.write("transfer 1: visible road: \n")
            f.write("transfer 1: outside of buffer: \n")
            f.write("transfer 1: inside basin: \n")
            f.write("transfer 1: sum slope: \n")
            f.write("transfer 1: max slope: \n")
            f.write("transfer 1: mean slope: \n")
            f.write("transfer 1: length line: \n")
        else:
            f.write("transfer 1: visible road: {}\n".format(visible_road[-1]))
            f.write("transfer 1: outside of buffer: {}\n".format(outside_of_buffer[-1]))
            f.write("transfer 1: inside basin: {}\n".format(inbasin[-1]))
            f.write("transfer 1: sum slope: {}\n".format(slope_sum[-1]))
            f.write("transfer 1: max slope: {}\n".format(slope_max[-1]))
            f.write("transfer 1: mean slope: {}\n".format(slope_mean[-1]))
            f.write("transfer 1: length line: {}\n".format(road_length[-1]))

        f.write("transfer 1: filtered scans: {}\n".format(filterResults))
        f.write("transfer 1: time: {}\n".format(timeToFinish))
