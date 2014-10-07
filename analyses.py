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

from scan_processing import remove_vector, get_environment, remove_temp_regions


def difference(real_elev, scanned_elev, new, env):
    """!Computes difference of original and scanned (scan - orig)."""
    info = grast.raster_info(real_elev)
    expression = "{new} = {scanned_elev} - {real_elev}".format(new=new, real_elev=real_elev,
                 scanned_elev=scanned_elev, max=info['max'], min=info['min'])
    gcore.run_command('r.mapcalc', expression=expression, overwrite=True, env=env)
    gcore.run_command('r.colors', map=new, color='differences', env=env)


def flowacc(scanned_elev, new, env):
    gcore.run_command('r.flow', elevation=scanned_elev, flowaccumulation=new, overwrite=True, env=env)


def slope(scanned_elev, new, env):
    gcore.run_command('r.slope.aspect', elevation=scanned_elev, slope=new, overwrite=True, env=env)


def aspect(scanned_elev, new, env):
    gcore.run_command('r.slope.aspect', elevation=scanned_elev, aspect=new, overwrite=True, env=env)
    
def slope_aspect(scanned_elev, slope, aspect, env):
    gcore.run_command('r.slope.aspect', elevation=scanned_elev, aspect=aspect, slope=slope, overwrite=True, env=env)


def shaded_relief(scanned_elev, new, zmult=10, env=None):
    gcore.run_command('r.shaded.relief', overwrite=True, input=scanned_elev, output=new, zmult=zmult, env=env)


def simwe(scanned_elev, depth, rain_value, niter, slope=None, aspect=None, env=None):
    pid = str(os.getpid())
    options = {}
    if slope:
        options['slope'] = slope
    if aspect:
        options['aspect'] = aspect
    gcore.run_command('r.slope.aspect', elevation=scanned_elev, dx='dx_' + pid, dy='dy' + pid, overwrite=True, env=env, **options)
    gcore.run_command('r.sim.water', elevation=scanned_elev, dx='dx_' + pid, dy='dy' + pid, rain_value=rain_value, depth=depth, nwalk=10000, niter=niter, overwrite=True, env=env)
    gcore.run_command('g.remove', rast=['dx_' + pid, 'dy' + pid])


def max_curv(scanned_elev, new, size=15, zscale=5, env=None):
    gcore.run_command('r.param.scale', overwrite=True, input=scanned_elev, output=new, size=size, param='maxic', zscale=zscale, env=env)
    gcore.run_command('r.colors', map=new, color='byr', env=env)


def landform(scanned_elev, new, size=25, zscale=1, env=None):
    gcore.run_command('r.param.scale', overwrite=True, input=scanned_elev, output=new, size=size, param='feature', zscale=zscale, env=env)


def geomorphon(scanned_elev, new, search=22, skip=12, flat=1, dist=0, env=None):
    gcore.run_command('r.geomorphon', overwrite=True, dem=scanned_elev, forms=new, search=search, skip=skip, flat=flat, dist=dist, env=env)


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
            gisenv = gcore.gisenv()
            path_to_vector = os.path.join(gisenv['GISDBASE'], gisenv['LOCATION_NAME'], gisenv['MAPSET'], 'vector', new)
            shutil.rmtree(path_to_vector)
        gcore.run_command('r.contour', input=scanned_elev, output=new, step=step, flags='t', env=env)
    except:
        # catching exception when a vector is added to GUI in the same time
        pass


def change_detection(before, after, change, height_threshold, cells_threshold, add, env):
    tmp_regions = []
    env = get_environment(tmp_regions, rast=before, n='n-30', s='s+30', e='e-30', w='w+30')
    diff_thr = 'diff_thr_' + str(os.getpid())
    diff_thr_clump = 'diff_thr_clump_' + str(os.getpid())
    change_vector = 'change_vector_' + str(os.getpid())
    if add:
        gcore.run_command('r.mapcalc', expression="{diff_thr} = if(({after} - {before}) > {thr1} &&"
                                                  " ({after} - {before}) < {thr2}, 1, null())".format(diff_thr=diff_thr,  after=after,
                                                                                                      before=before, thr1=height_threshold[0],
                                                                                                      thr2=height_threshold[1]), env=env)
    else:
        gcore.run_command('r.mapcalc', expression="{diff_thr} = if(({before} - {after}) > {thr}, 1, null())".format(diff_thr=diff_thr,
                          after=after, before=before, thr=height_threshold), env=env)
    gcore.run_command('r.clump', input=diff_thr, output=diff_thr_clump, env=env)

    stats = gcore.read_command('r.stats', flags='cn', input=diff_thr_clump, sort='desc', env=env).strip().split(os.linesep)
    if len(stats) > 0 and stats[0]:
        print stats
        cats = []
        for stat in stats:
            if float(stat.split()[1]) < cells_threshold[1] and float(stat.split()[1]) > cells_threshold[0]: # larger than specified number of cells
                cat, value = stat.split()
                cats.append(cat)
        if cats:
            expression = '{change} = if(('.format(change=change)
            for i, cat in enumerate(cats):
                if i != 0:
                    expression += ' || '
                expression += '{diff_thr_clump} == {val}'.format(diff_thr_clump=diff_thr_clump, val=cat)
            expression += '), 1, null())'
            gcore.run_command('r.mapcalc', overwrite=True, env=env, expression=expression)
            remove_vector(change_vector)
            gcore.run_command('r.to.vect', flags='st', input=change, output=change_vector, type='area', env=env)
            remove_vector(change)
            gcore.run_command('v.to.points', flags='t', input=change_vector, type='centroid', output=change, env=env)
            remove_vector(change_vector)
        else:
            gcore.warning("No change found!")
    else:
        gcore.warning("No change found!")
    
    gcore.run_command('g.remove', rast=[diff_thr, diff_thr_clump])
    remove_temp_regions(tmp_regions)


def trails_combinations(scanned_elev, friction, walk_coeff, _lambda, slope_factor,
                        walk, walking_dir, points, raster_route, vector_routes, env):
    import itertools
    coordinates = gcore.read_command('v.out.ascii', input=points, format='point', separator=',', env=env).strip()
    coords_list = []
    for coords in coordinates.split(os.linesep):
        coords_list.append(coords.split(',')[:2])

    remove_vector(vector_routes)
    gcore.run_command('v.edit', map=vector_routes, tool='create', env=env)
    vector_route_tmp = 'route_path_' + str(os.getpid())
    remove_vector(vector_route_tmp)

    for p1, p2 in itertools.combinations(coords_list, 2):
        p1 = ','.join(p1)
        p2 = ','.join(p2)
        trail(scanned_elev, friction, walk_coeff, _lambda, slope_factor, walk, walking_dir, p1, p2, raster_route, vector_route_tmp, env)
        gcore.run_command('v.patch', input=vector_route_tmp, output=vector_routes, flags='a', overwrite=True, env=env)
        remove_vector(vector_route_tmp)

    gcore.run_command('g.remove', rast=[walk, walking_dir, raster_route], env=env)

# procedure for finding a trail in real-time
def trail(scanned_elev, friction, walk_coeff, _lambda, slope_factor,
          walk, walking_dir, start, stop, raster_route, vector_route, env):
    gcore.run_command('r.walk',overwrite=True, flags='k', elevation=scanned_elev,
                      friction=friction, output=walk, outdir=walking_dir, start_coordinates=start,
                      stop_coordinates=stop, walk_coeff=walk_coeff, _lambda=_lambda, slope_factor=slope_factor, env=env)
    gcore.run_command('r.drain', overwrite=True, flags='d', input=walk, indir=walking_dir,
                      output=raster_route, vector_output=vector_route, start_coordinates=stop, env=env)
