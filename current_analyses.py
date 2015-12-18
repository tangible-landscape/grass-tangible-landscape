# -*- coding: utf-8 -*-
"""
This file serves as a control file with analyses
which are running in real-time. The name of the analyses
must start with 'run_'. The file has to be saved so that the change is applied.
"""
import subprocess

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
                                   height_threshold=10, filter_slope_threshold=10, add=True, env=env)
    habitat = 'habitat_block_clip'
    habitat_changed = 'habitat_changed'
    tmp_regions = []
    env1 = get_environment(tmp_regions, raster=habitat, n='n-200', s='s+200', e='e-200', w='w+200')
    gscript.mapcalc(exp="binary = if(not(isnull(change)), 1, 0)", env=env1)
    gscript.mapcalc(exp="{habitat_changed} = if(binary, 1, {habitat})".format(habitat=habitat, habitat_changed=habitat_changed), env=env1)
    gscript.run_command('r.colors', map=habitat_changed, raster=habitat, env=env1)
    remove_temp_regions(tmp_regions)



def model_termites(habitat_changed, init_colonies, output):
    tmp_regions = []
    env = get_environment(tmp_regions, raster=habitat_changed)
    subprocess.call(['Rscript', '/home/gis/Development/termites/CA_iso.R',
                     '--habitat=' + habitat_changed, '--sources=' + init_colonies, '--image=ortho.tiff', '--start=2003', '--end=2020',
                     '--tab=NewCol_table.csv', '--maxd=7', '--kdist=1000', '--output=' + output], env=env)
    gscript.run_command('t.create', output=output, title='title', description='descrition', env=env)
    maps = gscript.list_grouped('raster', pattern=output + "_*")[gscript.gisenv()['MAPSET']]
    gscript.run_command('t.register', input=output, maps=','.join(maps[1:]), env=env)
    gscript.run_command('t.rast.colors', input=output, rules='/home/gis/Development/termites/infection_colors.txt', env=env)
    remove_temp_regions(tmp_regions)
