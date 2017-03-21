# -*- coding: utf-8 -*-
"""
@brief experiment_freeplay.py

This program is free software under the GNU General Public License
(>=v2). Read the file COPYING that comes with GRASS for details.

@author: Anna Petrasova (akratoc@ncsu.edu)
"""

import grass.script as gscript
from experiment import updateProfile


def run_freeplay(real_elev, scanned_elev, eventHandler, env, **kwargs):
    gscript.run_command('g.copy', raster=[scanned_elev, 'freeplay_scan'], env=env)
    gscript.run_command('r.contour', input=scanned_elev, output='freeplay_contours', step=5, flags='t', env=env)

    event = updateProfile(points=[(640026, 223986), (640334, 223986)])
    eventHandler.postEvent(receiver=eventHandler.experiment_panel, event=event)
