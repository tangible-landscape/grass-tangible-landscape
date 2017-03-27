# -*- coding: utf-8 -*-
"""
@brief experiment_cutfill2

This program is free software under the GNU General Public License
(>=v2). Read the file COPYING that comes with GRASS for details.

@author: Anna Petrasova (akratoc@ncsu.edu)
"""

import os
from datetime import datetime
from analyses import get_environment
import grass.script as gscript


def run_cutfill(real_elev, scanned_elev, eventHandler, env, **kwargs):
    before_resampled = 'resamp'
    masked = 'masked'
    resulting = 'cutfill2_diff'
    gscript.run_command('r.resamp.interp', input=real_elev, output=before_resampled, env=env)
    gscript.mapcalc('{} = if(cutfill2_masking, {}, null())'.format(masked, before_resampled), env=env)
    coeff = gscript.parse_command('r.regression.line', mapx=scanned_elev, mapy=masked, flags='g', env=env)
    gscript.mapcalc(exp="{diff} = ({a} + {b} * {scan}) - {before}".format(diff=resulting, before=before_resampled, scan=scanned_elev,
                                                                          a=coeff['a'], b=coeff['b']), env=env)

    colors = ['100 black',
              '20 black',
              '7 red',
              '1 white',
              '0 white',
              '-1 white',
              '-7 blue',
              '-20 black',
              '-100 black',
              'nv black']
    gscript.write_command('r.colors', map=resulting, rules='-', stdin='\n'.join(colors), env=env)

    # copy scan
    postfix = datetime.now().strftime('%H_%M_%S')
    prefix = 'cutfill2'
    gscript.run_command('g.copy', raster=[scanned_elev, '{}_scan_{}'.format(prefix, postfix)], env=env)
    gscript.run_command('g.copy', raster=[resulting, '{}_diff_{}'.format(prefix, postfix)], env=env)


def post_cutfill(real_elev, scanned_elev, filterResults, timeToFinish, subTask, logDir, env):
    env2 = get_environment(raster=real_elev)
    gisenv = gscript.gisenv()
    logFile = os.path.join(logDir, 'log_{}_cutfill2.csv'.format(gisenv['LOCATION_NAME']))
    scoreFile = os.path.join(logDir, 'score_{}.csv'.format(gisenv['LOCATION_NAME']))
    scans = gscript.list_grouped(type='raster', pattern="*cutfill2_scan_*_*_*")[gisenv['MAPSET']]
    diffs = gscript.list_grouped(type='raster', pattern="*cutfill2_diff_*_*_*")[gisenv['MAPSET']]
    times = [each.split('_')[-3:] for each in scans]
    neg_volume = []
    pos_volume = []
    with open(logFile, 'w') as f:
        f.write('time,volume_positive,volume_negative\n')
        # if we need to speed up processing:
        last = 100
        for i in range(len(scans)):
            time = times[i]
            if i > len(scans) - last:
                threshold = 1
                env2 = get_environment(raster=diffs[i])
                gscript.mapcalc("diff_positive = if({diff} >= {thr}, {diff}, null())".format(diff=diffs[i], thr=threshold), env=env2)
                gscript.mapcalc("diff_negative = if({diff} <= -{thr}, abs({diff}), null())".format(diff=diffs[i], thr=threshold), env=env2)
                rinfo = gscript.raster_info(diffs[i])
                cell_area = rinfo['nsres'] * rinfo['ewres']
                pos_sum = float(gscript.parse_command('r.univar', map='diff_positive', flags='g', env=env2)['sum']) * cell_area
                pos_volume.append(pos_sum)
                neg_sum = float(gscript.parse_command('r.univar', map='diff_negative', flags='g', env=env2)['sum']) * cell_area
                neg_volume.append(neg_sum)
            else:
                pos_sum = neg_sum = ''
            f.write('{time},{volume_positive},{volume_negative}\n'.format(time='{}:{}:{}'.format(time[0], time[1], time[2]),
                    volume_positive=pos_sum, volume_negative=neg_sum))

    with open(scoreFile, 'a') as f:
        # test if participant did anything
        if len(scans) == 0:
            f.write("cutfill 2: diff negative volume: \n")
            f.write("cutfill 2: diff positive volume: \n")
            f.write("cutfill 2: filtered scans: {}\n".format(filterResults))
            f.write("cutfill 2: time since start: {}\n".format(timeToFinish))
            return

                # to make sure we don't get error if they skip quickly
        count = 2
        if len(scans) < count:
            # shouldn't happen
            count = len(scans)

        # here convert to some scale?
        mean_neg_volume = sum(neg_volume[-count:]) / float(count)
        mean_pos_volume = sum(pos_volume[-count:]) / float(count)
        f.write("cutfill 2: diff negative volume: {}\n".format(mean_neg_volume))
        f.write("cutfill 2: diff positive volume: {}\n".format(mean_pos_volume))
        f.write("cutfill 2: filtered scans: {}\n".format(filterResults))
        f.write("cutfill 2: time since start: {}\n".format(timeToFinish))
