# -*- coding: utf-8 -*-
"""
@brief experiment_cutfill2

This program is free software under the GNU General Public License
(>=v2). Read the file COPYING that comes with GRASS for details.

@author: Anna Petrasova (akratoc@ncsu.edu)
"""

import grass.script as gscript


def run_cutfill(real_elev, scanned_elev, eventHandler, env, **kwargs):
    before_resampled = 'resamp'
    masked = 'masked'
    gscript.run_command('r.resamp.interp', input=real_elev, output=before_resampled, env=env)
    gscript.mapcalc('{} = if(cutfill2_masking, {}, null())'.format(masked, before_resampled), env=env)
    coeff = gscript.parse_command('r.regression.line', mapx=scanned_elev, mapy=masked, flags='g', env=env)
    gscript.mapcalc(exp="{diff} = ({a} + {b} * {scan}) - {before}".format(diff='cutfill2_diff', before=before_resampled, scan=scanned_elev,
                                                                        a=coeff['a'], b=coeff['b']), env=env)

    colors = ['100 black',
              '15 black',
              '6 red',
              '0.5 white',
              '0 white',
              '-0.5 white',
              '-6 blue',
              '-15 black',
              '-100 black',
              'nv black']
    gscript.write_command('r.colors', map='cutfill2_diff', rules='-', stdin='\n'.join(colors), env=env)

def post_cutfill(real_elev, scanned_elev, filterResults, timeToFinish, subTask, logDir, env):
    # TODO
    return
