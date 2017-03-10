# -*- coding: utf-8 -*-
"""
@brief experiment_transferB

This program is free software under the GNU General Public License
(>=v2). Read the file COPYING that comes with GRASS for details.

@author: Anna Petrasova (akratoc@ncsu.edu)
"""
import os
from datetime import datetime
import grass.script as gscript
from experiment import updateDisplay
from tangible_utils import get_environment


def run_dams(real_elev, scanned_elev, eventHandler, env, **kwargs):
    filter_depth = 1
    repeat = 2
    input_dem = scanned_elev
    new = 'transfer_dam'
    output = "tmp_filldir"
    output2 = "tmp_filldir2"
    tmp_dir = "tmp_dir"
    for i in range(repeat):
        gscript.run_command('r.fill.dir', input=input_dem, output=output, direction=tmp_dir, env=env)
        input_dem = output
    gscript.mapcalc('{new} = if({out} - {scan} > {depth}, {out} - {scan}, null())'.format(new=output2, out=output, scan=scanned_elev, depth=filter_depth), env=env)

    gscript.mapcalc('{} = if({}, 1, null())'.format(output, output2), env=env)
    gscript.run_command('r.clump', input=output, output='clumps', env=env)
    stats = gscript.read_command('r.stats', flags='cn', input='clumps', sort='desc', env=env).strip().splitlines()
    if len(stats) > 0 and stats[0]:
        cats = []
        for stat in stats:
            if float(stat.split()[1]) > 80: # larger than specified number of cells
                cat, value = stat.split()
                cats.append(cat)
        if cats:
            expression = '{new} = if(('.format(new=new)
            for i, cat in enumerate(cats):
                if i != 0:
                    expression += ' || '
                expression += '{clump} == {val}'.format(clump='clumps', val=cat)
            expression += '), {}, null())'.format(output2)
            gscript.run_command('r.mapcalc', overwrite=True, env=env, expression=expression)
        else:
            gscript.mapcalc('{} = null()'.format(new), env=env)
            event = updateDisplay(value=None)
            eventHandler.postEvent(receiver=eventHandler.experiment_panel, event=event)
            return
        colors = ['0 179:235:243', '10 46:132:223', '20 11:11:147', '100 11:11:50']
        gscript.write_command('r.colors', map=new, rules='-', stdin='\n'.join(colors), env=env)
        data = gscript.parse_command('r.univar', map=new, flags='g', env=env)
        event = updateDisplay(value=float(data['n'])/100)
        found = True
        
    else:
        gscript.mapcalc('{} = null()'.format(new), env=env)
        event = updateDisplay(value=None)
        found = False

    eventHandler.postEvent(receiver=eventHandler.experiment_panel, event=event)

    # copy results
    if found:
        postfix = datetime.now().strftime('%H_%M_%S')
        prefix = 'transfer2'
        gscript.run_command('g.copy', raster=[scanned_elev, '{}_scan_{}'.format(prefix, postfix)], env=env)
        gscript.run_command('g.copy', raster=[new, '{}_dams_{}'.format(prefix, postfix)], env=env)


def post_transfer(real_elev, scanned_elev, filterResults, timeToFinish, subTask, logDir, env, **kwargs):
    gisenv = gscript.gisenv()
    logFile = os.path.join(logDir, 'log_{}_transfer2.csv'.format(gisenv['LOCATION_NAME']))
    scoreFile = os.path.join(logDir, 'score_{}.csv'.format(gisenv['LOCATION_NAME']))
    dams = gscript.list_grouped(type='raster', pattern="transfer2_dams_*_*_*")[gisenv['MAPSET']]

    times = [each.split('_')[-3:] for each in dams]
    score_volume = []
    score_area = []
    score_max = []
    with open(logFile, 'w') as f:
        f.write('time,dam_volume,dam_area,dam_max\n')
        for i in range(len(dams)):
            env2 = get_environment(raster=dams[i])
            data_dams = gscript.parse_command('r.univar', map=dams[i], flags='g', env=env2)
            rinfo = gscript.raster_info(dams[i])
            cell_area = rinfo['nsres'] * rinfo['ewres']
            volume = float(data_dams['sum']) * cell_area
            area = float(data_dams['n']) * cell_area
            max_depth = float(data_dams['max'])
            score_volume.append(volume)
            score_area.append(area)
            score_max.append(max_depth)
            time = times[i]
            f.write('{time},{dam_volume},{dam_area},{dam_max}\n'.format(time='{}:{}:{}'.format(time[0], time[1], time[2]),
                    dam_volume=volume,
                    dam_area=area,
                    dam_max=max_depth))

    with open(scoreFile, 'a') as f:
        # to make sure we don't get error if they skip quickly
        count = 3
        if len(score_volume) < count:
            # shouldn't happen
            count = len(score_volume)

        # here convert to some scale?
        mean_volume = sum(score_volume[-count:]) / float(count)
        mean_area = sum(score_area[-count:]) / float(count)
        max_depth = max(score_max[-count:])
        f.write("transfer 2: volume: {}\n".format(mean_volume))
        f.write("transfer 2: area: {}\n".format(mean_area))
        f.write("transfer 2: max depth: {}\n".format(max_depth))
        f.write("transfer 2: filtered scans: {}\n".format(filterResults))
        f.write("transfer 2: time: {}\n".format(timeToFinish))
