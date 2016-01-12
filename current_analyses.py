# -*- coding: utf-8 -*-
"""
This file serves as a control file with analyses
which are running in real-time. The name of the analyses
must start with 'run_'. The file has to be saved so that the change is applied.
"""
import subprocess
import os
import analyses
from utils import get_environment, remove_temp_regions
import grass.script as gscript


#def run_difference(real_elev, scanned_elev, env, **kwargs):
#    analyses.difference(real_elev=real_elev, scanned_elev=scanned_elev, env=env, new='diff')
#    
#
#def run_contours(scanned_elev, env, **kwargs):
#    analyses.contours(scanned_elev=scanned_elev, new='contours_scanned', env=env, step=2)
#
#    
#def run_simwe(scanned_elev, env, **kwargs):
#    analyses.simwe(scanned_elev=scanned_elev, depth='depth', rain_value=300, niterations=4, env=env)
#
#
#def run_erosion(scanned_elev, env, **kwargs):
#    analyses.erosion(scanned_elev=scanned_elev, rain_value=200, depth='depth', detachment_coeff=0.001, transport_coeff=0.01, shear_stress=0, sediment_flux='flux', erosion_deposition='erdep', niterations=4, env=env)  
#def run_geomorphon(scanned_elev, env, **kwargs):
#    analyses.geomorphon(scanned_elev, new='geomorphon', search=22, skip=12, flat=1, dist=0, env=env)

#def run_slope_aspect(scanned_elev, env, **kwargs):
#    analyses.slope_aspect(scanned_elev=scanned_elev, slope='slope', aspect='aspect', env=env)

#    
#def run_usped(scanned_elev, env, **kwargs):
#    analyses.flowacc(scanned_elev, new='flowacc', env=env)
#    analyses.usped(scanned_elev, k_factor='soils_Kfactor', c_factor='cfactorbare_1m', flowacc='flowacc', slope='slope', aspect='aspect', new='erdep', env=env)

#def run_change_detection(scanned_elev, env, **kwargs):
#    analyses.change_detection(before='scan', after=scanned_elev,
#                              change='change', height_threshold=[10, 30], cells_threshold=[10, 200], add=True, max_detected=6, env=env)
#
#                              
#def run_trail(real_elev, scanned_elev, env, **kwargs):
#    analyses.trails_combinations(real_elev,friction='friction', walk_coeff=[0.72, 6.0, 1.9998, -1.9998],
#                                 _lambda=.5, slope_factor=-.8125, walk='walk_result',
#                                 walking_dir='walkdir_result', points='change', raster_route='route_result',
#                                 vector_routes='route_result', mask=None, env=env)
#    analyses.trail_salesman(trails='route_result', points='change', output='route_salesman', env=env)

#def run_viewshed(real_elev, scanned_elev, env, **kwargs):
#    analyses.viewshed(real_elev, output='viewshed', obs_elev=1.75, vector='change', visible_color='green', invisible_color='red', env=env)

#def run_subsurface(scanned_elev, env, **kwargs):
#    voxel = 'interp_no_terrain_2002_08_25@soils_base_data'
#
#    analyses.cross_section(scanned_elev=scanned_elev, voxel=voxel, new='cross', env=env)
#    analyses.contours(scanned_elev=scanned_elev, new='scanned_contours', step=5., maxlevel=0, env=env)

def run_prepare_termites(scanned_elev, env, **kwargs):
    analyses.change_detection_area(before='scan_saved', after=scanned_elev, change='change',
                                   height_threshold=20, filter_slope_threshold=30, add=True, env=env)
    habitat = 'unsuitable_habitat'
    habitat_changed = 'habitat_changed'
    tmp_regions = []
    #env1 = get_environment(tmp_regions, raster=habitat, n='n-200', s='s+200', e='e-200', w='w+200')
    env2 = get_environment(tmp_regions, raster=habitat)
    gscript.mapcalc(exp="binary = if(not(isnull(change)), 1, 0)", env=env2)
    gscript.mapcalc(exp="{habitat_changed} = if(binary, 1, {habitat})".format(habitat=habitat, habitat_changed=habitat_changed), env=env2)
    gscript.run_command('r.colors', map=habitat_changed, raster=habitat, env=env2)
    remove_temp_regions(tmp_regions)



def model_termites(habitat_changed, init_colonies, output, round):
    tmp_regions = []
    env = get_environment(tmp_regions, raster=habitat_changed)
    name = output.split('@')[0] + "_" + str(round)
    subprocess.call(['Rscript', '/home/gis/Development/termites/CA_iso.R',
                     '--habitat=' + habitat_changed, '--sources=' + init_colonies, '--image=ortho.tiff', '--start=2003', '--end=2040',
                     '--tab=NewCol_table.csv', '--ktype=gauss', '--surv=0.01', '--maxd=10', '--kdist=100', '--output=' + name], env=env)
    gscript.run_command('t.create', output=name, title='title', description='descrition', env=env)
    maps = gscript.list_grouped('raster', pattern=name + "_*")[gscript.gisenv()['MAPSET']]
    #gscript.run_command('t.register', input=name, maps=','.join(maps[1:]), env=env)
    #gscript.run_command('t.rast.colors', input=name, rules='/home/gis/Development/termites/infection_colors.txt', env=env)
    #last = gscript.read_command('t.rast.list',  input=name, columns='name', method='comma', env=env).strip().split(',')[-1]
    last = maps[-1]
    gscript.run_command('r.colors', map=','.join(maps[1:]), rules='/home/gis/Development/termites/infection_colors.txt', env=env)
    gscript.run_command('g.copy', raster=[last, 'result'], env=env)
    area = float(gscript.parse_command('r.univar', map=last, flags='g', env=env)['n'])
    treatment_area = int(gscript.parse_command('r.univar', map=habitat_changed, flags='g', env=env)['n']) - 396
    before = ''
    if round > 1:
        before = gscript.read_command('v.db.select', flags='c', map='score', columns='area', env=env).strip() + "   "
    gscript.run_command('v.db.update', map='score', layer=1, column='area', value=before + str(round) + ': ' + str(int(area)), env=env)
    
    # save results
    if round == 1:
        gscript.run_command('g.copy', vector=[init_colonies.split('@')[0], init_colonies.split('@')[0] + output.split('@')[0]], env=env)
    if round > 1:
        gscript.run_command('g.copy', raster=[habitat_changed.split('@')[0], habitat_changed.split('@')[0] + name], env=env)
    path = '/home/gis/Desktop/results.csv'
    if not os.path.exists(path):
        with open(path, 'w') as f:
            pass
    with open(path, 'a') as f:
        f.write(name + ',' + str(area) + ',' + str(treatment_area) + '\n')
    remove_temp_regions(tmp_regions)
