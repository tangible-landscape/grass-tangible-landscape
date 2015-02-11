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
    gcore.run_command('r.colors', map=aspect, color='aspectcolr', env=env)


def shaded_relief(scanned_elev, new, zscale=10, env=None):
    gcore.run_command('r.shaded.relief', overwrite=True, input=scanned_elev, output=new, zscale=zscale, env=env)


def simwe(scanned_elev, depth, rain_value, niterations, slope=None, aspect=None, env=None):
    pid = str(os.getpid())
    options = {}
    if slope:
        options['slope'] = slope
    if aspect:
        options['aspect'] = aspect
    gcore.run_command('r.slope.aspect', elevation=scanned_elev, dx='dx_' + pid, dy='dy' + pid, overwrite=True, env=env, **options)
    gcore.run_command('r.sim.water', elevation=scanned_elev, dx='dx_' + pid, dy='dy' + pid, rain_value=rain_value, depth=depth, nwalkers=10000, niterations=niterations, overwrite=True, env=env)
    gcore.run_command('g.remove', flags='f', type='raster', name=['dx_' + pid, 'dy' + pid])


def erosion(scanned_elev, rain_value, depth, detachment_coeff, transport_coeff, shear_stress, niterations, sediment_flux, erosion_deposition, slope=None, aspect=None, env=None):
    pid = str(os.getpid())
    options = {}
    if slope:
        options['slope'] = slope
    if aspect:
        options['aspect'] = aspect
    dc, tc, tau = 'dc' + pid, 'tc' + pid, 'tau' + pid
    gcore.run_command('r.slope.aspect', elevation=scanned_elev, dx='dx_' + pid, dy='dy' + pid, overwrite=True, env=env, **options)
    gcore.run_command('r.sim.water', elevation=scanned_elev, dx='dx_' + pid, dy='dy' + pid, rain_value=rain_value, depth=depth, nwalkers=10000, niterations=niterations, overwrite=True, env=env)
    gcore.run_command('r.mapcalc', expression="{dc} = {detachment_coeff}".format(dc=dc, detachment_coeff=detachment_coeff), overwrite=True, env=env)
    gcore.run_command('r.mapcalc', expression="{tc} = {transport_coeff}".format(tc=tc, transport_coeff=transport_coeff), overwrite=True, env=env)
    gcore.run_command('r.mapcalc', expression="{tau} = {shear_stress}".format(tau=tau, shear_stress=shear_stress), overwrite=True, env=env)
    gcore.run_command('r.sim.sediment', elevation=scanned_elev, dx='dx_' + pid, dy='dy' + pid, water_depth=depth, detachment_coeff=dc, transport_coeff=tc, shear_stress=tau, sediment_flux=sediment_flux, erosion_deposition=erosion_deposition, niterations=niterations, nwalkers=10000, overwrite=True, env=env)
    gcore.run_command('g.remove', flags='f', type='raster', name=[dc, tc, tau, 'dx_' + pid, 'dy' + pid], env=env)


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

    gcore.run_command('g.remove', flags='f', type='raster', name=[sedflow, qsx, qsxdx, qsy, qsydy, slope_sm])


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

def change_detection_area(before, after, change, height_threshold, add, env):
    """Detects change in area. Result are areas with value
    equals the max difference between the scans as a positive value."""
    slope = 'slope_tmp_get_change'
    changes = 'found_tmp_get_change'
    changes_singleval = 'found_singleval_tmp_get_change'
    changes_clumped = 'found_clumped_tmp_get_change'
    changes_max = 'found_max_tmp_get_change'

    # slope is used to filter areas of change with high slope (edge of model)
    gcore.run_command('r.slope.aspect', elevation=scan_before, slope=slope, env=env)
    if not add:
        after, before = before, after

    grast.mapcalc(exp="{changes} = if({slope} < 50 && {before} - {after} > {min_z_diff}, {before} - {after}, null());"
                      "{changes_singleval} = if({slope} < 50 && ({before} - {after}) > {min_z_diff}, 1, null())".format(
                          changes=changes, slope=slope, before=scan_before, after=scan_after, min_z_diff=height_threshold,
                          changes_singleval=changes_singleval), env=env)

    gcore.run_command('r.clump', input=changes_singleval, output=changes_clumped, env=env)
    gcore.run_command('r.stats.zonal', base=changes_clumped, cover=changes,
                      method='max', output=changes_max, env=env)
    # this is an addon, must be installed!
    gcore.run_command('r.grow.shrink', input=changes_max, output=change, env=env)

    gcore.run_command('g.remove', type='raster', pattern="*tmp_get_change", flags='f')

def detect_markers(scanned_elev, points, slope_threshold, save_height, env):
    """Detects markers based on current scan only (no difference)."""
    slope = 'slope_tmp_get_marker'
    range = 'range_tmp_get_marker'
    slope_sum = 'slope_sum_tmp_get_marker'
    flowacc = 'flowacc_tmp_get_marker'
    raster_points = "raster_points_tmp_get_marker"

    save_height = True
    gcore.run_command('r.watershed', elevation=scanned_elev, accumulation=flowacc, env=env)
    gcore.run_command('r.slope.aspect', elevation=scanned_elev, slope=slope, env=env)
    gcore.run_command('r.neighbors', input=slope, method='median',
                      output=slope_sum, size=5, flags='c', env=env)
    if save_height:
        gcore.run_command('r.neighbors', input=scanned_elev, method='range',
                          output=range, size=13, env=env)

    if save_height:
        range_ = range
    else:
        range_ = 1

    grast.mapcalc(exp='{raster_points} = if({flowacc} == 1 && {slope_sum} > {slope_threshold}, {range}, null())'.format(
                  raster_points=raster_points, flowacc=flowacc, slope_sum=slope_sum,
                  slope_threshold=slope_threshold, range=range_), env=env)

    options = {}
    if save_height:
        options['column'] = 'height'

    gcore.run_command('r.to.vect', input=raster_points, output=points, type='point', env=env, **options)
    gcore.run_command('g.remove', type='raster', pattern="*tmp_get_marker", flags='f')


def change_detection(before, after, change, height_threshold, cells_threshold, add, max_detected, env):
    tmp_regions = []
    env = get_environment(tmp_regions, rast=before, n='n-20', s='s+20', e='e-20', w='w+20')
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
        found = 0
        for stat in stats:
            if found >= max_detected:
                break
            if float(stat.split()[1]) < cells_threshold[1] and float(stat.split()[1]) > cells_threshold[0]: # larger than specified number of cells
                found += 1
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
    
    gcore.run_command('g.remove', flags='f', type='raster', name=[diff_thr, diff_thr_clump])
    remove_temp_regions(tmp_regions)


def trails_combinations(scanned_elev, friction, walk_coeff, _lambda, slope_factor,
                        walk, walking_dir, points, raster_route, vector_routes, mask, env):
    import itertools

    coordinates = gcore.read_command('v.out.ascii', input=points, format='point', separator=',', env=env).strip()
    coords_list = []
    for coords in coordinates.split(os.linesep):
        coords_list.append(coords.split(',')[:2])

    combinations = itertools.combinations(coords_list, 2)
    combinations = [list(group) for k, group in itertools.groupby(combinations, key=lambda x: x[0])]
    i = k = 0
    vector_routes_list = []

    walk_tmp = 'walk_tmp'
    walk_dir_tmp = 'walk_dir_tmp'
    raster_route_tmp = 'raster_route_tmp'
    
    if mask:
        gcore.message('Activating mask')
        gcore.run_command('r.mask', raster=mask, overwrite=True, env=env)
    for points in combinations:
        i += 1
        point_from = ','.join(points[0][0])
        points_to = [','.join(pair[1]) for pair in points]
        vector_routes_list_drain = []
        for each in points_to:
            vector_route_tmp = 'route_path_' + str(k)
            remove_vector(vector_route_tmp)
            vector_routes_list_drain.append(vector_route_tmp)
            k += 1
        vector_routes_list.extend(vector_routes_list_drain)

        trail(scanned_elev, friction, walk_coeff, _lambda, slope_factor,
              walk_tmp, walk_dir_tmp, point_from, points_to, raster_route_tmp, vector_routes_list_drain, env)
    remove_vector(vector_routes)          
    gcore.run_command('v.patch', input=vector_routes_list, output=vector_routes, overwrite=True, env=env)

    gcore.run_command('g.remove', flags='f', type='raster', name=[walk_tmp, walk_dir_tmp, raster_route_tmp], env=env)
    gcore.message('Removing mask')
    if mask:
        gcore.run_command('r.mask', flags='r', env=env)
    for vmap in vector_routes_list:
        remove_vector(vmap)


# procedure for finding a trail in real-time
def trail(scanned_elev, friction, walk_coeff, _lambda, slope_factor,
          walk, walk_dir, point_from, points_to, raster_route, vector_routes, env):
    gcore.run_command('r.walk',overwrite=True, flags='k', elevation=scanned_elev,
                      friction=friction, output=walk, start_coordinates=point_from, outdir=walk_dir, 
                      stop_coordinates=points_to, walk_coeff=walk_coeff, _lambda=_lambda, slope_factor=slope_factor, env=env)
    for i in range(len(points_to)):
        gcore.run_command('r.drain', overwrite=True, input=walk, indir=walk_dir, flags='d', vector_output=vector_routes[i],
                          output=raster_route, start_coordinates=points_to[i], env=env)

def trail_salesman(trails, points, output, env):
    net_tmp = 'net_tmp'
    gcore.run_command('v.net', input=trails, points=points, output=net_tmp,
                      operation='connect', threshold=10, overwrite=True, env=env)
    cats = gcore.read_command('v.category', input=net_tmp, layer=2,
                              option='print').strip().split(os.linesep)
    gcore.run_command('v.net.salesman', input=net_tmp, output=output,
                      ccats=','.join(cats), alayer=1, nlayer=2, overwrite=True)
    remove_vector(net_tmp)


def viewshed(scanned_elev, output, vector, visible_color, invisible_color, obs_elev=1.7, env=None):   
    coordinates = gcore.read_command('v.out.ascii', input=vector, separator=',', env=env).strip()
    coordinate = None
    for line in coordinates.split(os.linesep):
        coordinate = [float(c) for c in line.split(',')[0:2]]
        break
    if coordinate:
        gcore.run_command('r.viewshed', flags='b', input=scanned_elev, output=output, coordinates=coordinate, observer_elevation=obs_elev, env=env, overwrite=True)
        gcore.run_command('r.null', map=output, null=0)
        gcore.write_command('r.colors', map=output,  rules='-', stdin='0 {invis}\n1 {vis}'.format(vis=visible_color, invis=invisible_color), env=env)
