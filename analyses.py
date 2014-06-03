# -*- coding: utf-8 -*-
"""
@brief Available analyses (wrapper around GRASS modules or chains of tools)

This program is free software under the GNU General Public License
(>=v2). Read the file COPYING that comes with GRASS for details.

@author: Anna Petrasova (akratoc@ncsu.edu)
"""
import os
import shutil

from grass.script import core as gcore
from grass.script import raster as grast


def difference(real_elev, scanned_elev, new, env):
    """!Computes difference of original and scanned (scan - orig)."""
    info = grast.raster_info(real_elev)
    expression = "{new} = {scanned_elev} - {real_elev}".format(new=new, real_elev=real_elev,
                 scanned_elev=scanned_elev, max=info['max'], min=info['min'])
    gcore.run_command('r.mapcalc', expression=expression, overwrite=True, env=env)
    gcore.run_command('r.colors', map=new, color='differences', env=env)


def smooth(scanned_elev, new, env):
    gcore.run_command('r.neighbors', input=scanned_elev, output=new, size=9, overwrite=True, env=env)


def flowacc(scanned_elev, new, env):
    gcore.run_command('r.flow', elevation=scanned_elev, flowaccumulation=new, overwrite=True, env=env)


def slope(scanned_elev, new, env):
    gcore.run_command('r.slope.aspect', elevation=scanned_elev, slope=new, overwrite=True, env=env)


def aspect(scanned_elev, new, env):
    gcore.run_command('r.slope.aspect', elevation=scanned_elev, aspect=new, overwrite=True, env=env)
    
def slope_aspect(scanned_elev, slope, aspect, env):
    gcore.run_command('r.slope.aspect', elevation=scanned_elev, aspect=aspect, slope=slope, overwrite=True, env=env)


def shaded_relief(scanned_elev, new, env):
    gcore.run_command('r.shaded.relief', overwrite=True, input=scanned_elev, output=new, zmult=10, env=env)


def simwe(scanned_elev, depth, env, slope=None, aspect=None):
    pid = str(os.getpid())
    options = {}
    if slope:
        options['slope'] = slope
    if aspect:
        options['aspect'] = aspect
    gcore.run_command('r.slope.aspect', elevation=scanned_elev, dx='dx_' + pid, dy='dy' + pid, overwrite=True, env=env, **options)
    gcore.run_command('r.sim.water', elevation=scanned_elev, dx='dx_' + pid, dy='dy' + pid, rain_value=500, depth=depth, nwalk=10000, niter=4, overwrite=True, env=env)
    gcore.run_command('g.remove', rast=['dx_' + pid, 'dy' + pid])


def max_curv(scanned_elev, new, env):
    gcore.run_command('r.param.scale', overwrite=True, input=scanned_elev, output=new, size=15, param='maxic', zscale=5, env=env)
    gcore.run_command('r.colors', map=new, color='byr', env=env)


def landform(scanned_elev, new, env):
    gcore.run_command('r.param.scale', overwrite=True, input=scanned_elev, output=new, size=25, param='feature', zscale=1, env=env)


def geomorphon(scanned_elev, new, env):
    gcore.run_command('r.geomorphon', overwrite=True, dem=scanned_elev, forms=new, search=22, skip=12, flat=1, dist=0, env=env)


def usped(scanned_elev, k_factor, c_factor, flowacc, slope, aspect, new, env):
    """!Computes net erosion and deposition (USPED model)"""
    sedflow = 'sedflow_' + str(os.getpid())
    qsx = 'qsx_' + str(os.getpid())
    qsxdx = 'qsxdx_' + str(os.getpid())
    qsy = 'qsy_' + str(os.getpid())
    qsydy = 'qsydy_' + str(os.getpid())
    slope_sm = 'slope_sm' + str(os.getpid())
    gcore.run_command('r.neighbors', overwrite=True, input=slope, output=slope_sm, size=5, env=env)
    gcore.run_command('r.mapcalc', expression="{sedflow} = 270. * {k_factor} * {c_factor} * {flowacc} * sin({slope})".format(c_factor=c_factor, k_factor=k_factor, slope=slope_sm, flowacc=flowacc, sedflow=sedflow), overwrite=True, env=env)
    gcore.run_command('r.mapcalc', expression="{qsx} = {sedflow} * cos({aspect})".format(sedflow=sedflow, aspect=aspect, qsx=qsx), overwrite=True, env=env)
    gcore.run_command('r.mapcalc', expression="{qsy} = {sedflow} * sin({aspect})".format(sedflow=sedflow, aspect=aspect, qsy=qsy), overwrite=True, env=env)
    gcore.run_command('r.slope.aspect', elevation=qsx, dx=qsxdx, overwrite=True, env=env)
    gcore.run_command('r.slope.aspect', elevation=qsy, dy=qsydy, overwrite=True, env=env)
    gcore.run_command('r.mapcalc', expression="{erdep} = {qsxdx} + {qsydy}".format(erdep=new, qsxdx=qsxdx, qsydy=qsydy), overwrite=True, env=env)
    gcore.write_command('r.colors', map=new,  rules='-', stdin='-15000 100 0 100\n-100 magenta\n-10 red\n-1 orange\n-0.1 yellow\n0 200 255 200\n0.1 cyan\n1 aqua\n10 blue\n100 0 0 100\n18000 black', env=env)

    gcore.run_command('g.remove', rast=[sedflow, qsx, qsxdx, qsy, qsydy, slope_sm])


def contours(scanned_elev, new, env, step=None):
    if not step:
        info = grast.raster_info(scanned_elev)
        step = (info['max'] - info['min']) / 12.
    try:
        if gcore.find_file(new, element='vector')['name']:
            gcore.run_command('v.db.droptable', map=new, flags='f', env=env)
            gisenv = gcore.gisenv()
            path_to_vector = os.path.join(gisenv['GISDBASE'], gisenv['LOCATION_NAME'], gisenv['MAPSET'], 'vector', new)
            shutil.rmtree(path_to_vector)
        gcore.run_command('r.contour', input=scanned_elev, output=new, step=step, env=env)
    except:
        # catching exception when a vector is added to GUI in the same time
        pass


def change_detection(before, after, change, height_treshold, add, env):
    diff_thr = 'diff_thr_' + str(os.getpid())
    diff_thr_clump = 'diff_thr_clump_' + str(os.getpid())
    if add:
        gcore.run_command('r.mapcalc', expression="{diff_thr} = if(({after} - {before}) > {thr}, 1, null())".format(diff_thr=diff_thr,  after=after, before=before, thr=height_treshold), env=env)
    else:
        gcore.run_command('r.mapcalc', expression="{diff_thr} = if(({before} - {after}) > {thr}, 1, null())".format(diff_thr=diff_thr,  after=after, before=before, thr=height_treshold), env=env)
    gcore.run_command('r.clump', input=diff_thr, output=diff_thr_clump, env=env)
    stats = gcore.read_command('r.stats', flags='cn', input=diff_thr_clump, sort='desc', env=env).strip().split('\n')
    if len(stats) > 0:
        print stats
        cat, value = stats[0].split()
    gcore.run_command('r.mapcalc', expression="{change} = if({diff_thr_clump} == {val}, 1, null())".format(change=change,  diff_thr_clump=diff_thr_clump, val=cat), overwrite=True, env=env)
    gcore.run_command('g.remove', rast=[diff_thr, diff_thr_clump])
