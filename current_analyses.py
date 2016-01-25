# -*- coding: utf-8 -*-
"""
This file serves as a control file with analyses
which are running in real-time. The name of the analyses
must start with 'run_'. The file has to be saved so that the change is applied.
"""
import subprocess
import uuid

import analyses
from tangible_utils import get_environment, remove_temp_regions
import grass.script as gscript
from grass.exceptions import CalledModuleError


#def run_difference(real_elev, scanned_elev, env, **kwargs):
#    analyses.difference(real_elev=real_elev, scanned_elev=scanned_elev, env=env, new='diff')
#    
#
#def run_contours(scanned_elev, env, **kwargs):
#    analyses.contours(scanned_elev=scanned_elev, new='contours_scanned', env=env, step=2)


#def run_ponds(scanned_elev, env, **kwargs):
#    analyses.depression(scanned_elev=scanned_elev, new="ponds", repeat=2, filter_depth=0.1, env=env)
#
#def run_rlake(real_elev, scanned_elev, env, **kwargs):
#    seed = [703758.79476,11471.6200873]
#    analyses.rlake(scanned_elev, new='lake', base=real_elev, env=env, seed=seed, level=3)


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
#    tmp_regions = []
#    env = get_environment(tmp_regions, rast3d=voxel, nsres=3, ewres=3)
#    analyses.cross_section(scanned_elev=scanned_elev, voxel=voxel, new='cross', env=env)
#    analyses.contours(scanned_elev=scanned_elev, new='contours_scanned', step=5., maxlevel=0, env=env)
#    remove_temp_regions(tmp_regions)
