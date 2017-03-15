# -*- coding: utf-8 -*-
"""
@brief experiment_flow

This program is free software under the GNU General Public License
(>=v2). Read the file COPYING that comes with GRASS for details.

@author: Anna Petrasova (akratoc@ncsu.edu)
"""
import os
from datetime import datetime
from tangible_utils import get_environment
import grass.script as gscript


def run_contours(real_elev, scanned_elev, eventHandler, env, **kwargs):
    gscript.run_command('r.contour', input=scanned_elev, output='flow_contours', step=5, flags='t', env=env)


def run_flow(real_elev, scanned_elev, eventHandler, env, **kwargs):
    gscript.run_command('r.slope.aspect', elevation=scanned_elev, dx='dx', dy='dy', env=env)
    gscript.run_command('r.sim.water', elevation=scanned_elev, dx='dx', dy='dy', rain_value=300,
                        depth='flow_flow', niterations=6, env=env)
    gscript.write_command('r.colors', map='flow_flow', rules='-',
                          stdin='0.001 156:255:2\n0.05 0:255:255\n0.1 0:127:255\n0.5 0:0:255\n10 0:0:0', env=env)
    # copy scan
    postfix = datetime.now().strftime('%H_%M_%S')
    prefix = 'flow'
    gscript.run_command('g.copy', raster=[scanned_elev, '{}_scan_{}'.format(prefix, postfix)], env=env)


def post_flow(real_elev, scanned_elev, filterResults, timeToFinish, logDir, env, **kwargs):
#    gscript.run_command('r.slope.aspect', elevation=scanned_elev, dx='dx', dy='dy', env=env)
#    gscript.run_command('r.sim.water', elevation=scanned_elev, dx='dx', dy='dy', rain='flow_rain',
#                        depth='flow_flow_final', niterations=200, diffusion_coeff=1, hmax=0.15, halpha=8, env=env)

    env2 = get_environment(raster='flow_dem')
    gscript.run_command('r.resamp.interp', input='scan', output='scan_resampled', env=env2)
    gscript.run_command('r.watershed', flags='as', elevation='scan_resampled', flow='flow_rain', accumulation='flow_flow_final_sfd', env=env2)
    gscript.run_command('r.watershed', flags='a', elevation='scan_resampled', flow='flow_rain', accumulation='flow_flow_final_mfd', env=env2)
    # water in target area 
    gscript.run_command('r.mask', vector='flow_target_buffer', env=env2)
    max_flowacc = gscript.parse_command('r.univar', map='flow_flow_final_sfd', flags='g', env=env2)['max']
    sum_flowacc = gscript.parse_command('r.univar', map='flow_flow_final_mfd', flags='g', env=env2)['sum']
    gscript.run_command('r.mask', flags='r', env=env2)
    gscript.run_command('r.mask', raster='flow_edge', env=env2)
    sum_sfd_edge = gscript.parse_command('r.univar', map='flow_flow_final_sfd', flags='g', env=env2)['sum']
    sum_mfd_edge = gscript.parse_command('r.univar', map='flow_flow_final_mfd', flags='g', env=env2)['sum']
    gscript.run_command('r.mask', flags='r', env=env2)

    # difference
    regression='flow_regression'
    gscript.run_command('r.mask', vector='flow_rain', env=env)
    regression_params = gscript.parse_command('r.regression.line', flags='g', mapx=scanned_elev, mapy='scan_saved', env=env)
    gscript.run_command('r.mask', flags='r', env=env)
    gscript.mapcalc('{regression} = {a} + {b} * {before}'.format(a=regression_params['a'], b=regression_params['b'],
                    before=scanned_elev, regression=regression), env=env)
    gscript.mapcalc('flow_difference = {regression} - {after}'.format(regression=regression, after='scan_saved'), env=env)       
    gscript.mapcalc('flow_difference_positive = if(flow_difference > 5, flow_difference, null())', env=env)
    gscript.mapcalc('flow_difference_negative = if(flow_difference <= -5, abs(flow_difference), null())', env=env)
    diff_pos = gscript.parse_command('r.univar', map='flow_difference_positive', flags='g')['sum']
    diff_neg = gscript.parse_command('r.univar', map='flow_difference_negative', flags='g')['sum']

    gisenv = gscript.gisenv()
    logFile = os.path.join(logDir, 'log_{}_flow.csv'.format(gisenv['LOCATION_NAME']))
    scoreFile = os.path.join(logDir, 'score_{}.csv'.format(gisenv['LOCATION_NAME']))
    scans = gscript.list_grouped(type='raster', pattern="flow_scan_*_*_*")[gisenv['MAPSET']]
    t = scans[-1].split('_')[-3:]
    with open(logFile, 'w') as f:
        f.write('time\n')
        f.write('{}:{}:{}\n'.format(t[0], t[1], t[2]))

    with open(scoreFile, 'a') as f:
        f.write("flow: difference positive: {}\n".format(float(diff_pos)))
        f.write("flow: difference negative: {}\n".format(float(diff_neg)))
        f.write("flow: water max sfd: {}\n".format(float(max_flowacc)))
        f.write("flow: water sum mfd: {}\n".format(float(sum_flowacc)))
        f.write("flow: water edge sum sfd: {}\n".format(float(sum_sfd_edge)))
        f.write("flow: water edge sum mfd: {}\n".format(float(sum_mfd_edge)))
        f.write("filtered scans: {}\n".format(filterResults))
        f.write("time: {}\n".format(timeToFinish))
