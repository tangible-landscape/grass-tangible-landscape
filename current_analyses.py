# -*- coding: utf-8 -*-
"""
This file serves as a control file with analyses
which are running in real-time. The name of the analyses
must start with 'run_'. The file has to be saved so that the change is applied.

Each `run_*` function receives `tools` (a grass.tools.Tools instance bound to a
fresh region/mask context) and `env` (the underlying environment dict) plus
the per-call kwargs from the dispatcher. The simplest pattern is to forward
`tools=tools` to the analyses helpers; pass `env` as well only when you need
to wrap the call in a RegionManager / MaskManager.
"""
import subprocess  # noqa: F401
import uuid  # noqa: F401

import analyses  # noqa: F401
import grass.script as gs  # noqa: F401
from grass.script import RegionManager, MaskManager  # noqa: F401
from grass.tools import Tools, ToolError  # noqa: F401
from grass.exceptions import CalledModuleError  # noqa: F401


# def run_difference(real_elev, scanned_elev, tools, **kwargs):
#     analyses.difference(real_elev=real_elev, scanned_elev=scanned_elev,
#                         new='diff', zexag=1, tools=tools)
#
#
# def run_contours(scanned_elev, tools, **kwargs):
#     analyses.contours(scanned_elev=scanned_elev, new='contours_scanned',
#                       step=2, tools=tools)


# def run_ponds(scanned_elev, tools, **kwargs):
#     analyses.depression(scanned_elev=scanned_elev, new='ponds', repeat=2,
#                         filter_depth=0.1, tools=tools)
#
# def run_rlake(real_elev, scanned_elev, tools, **kwargs):
#     seed = [703758.79476, 11471.6200873]
#     analyses.rlake(scanned_elev=scanned_elev, new='lake', base=real_elev,
#                    seed=seed, level=3, tools=tools)


# def run_simwe(scanned_elev, tools, **kwargs):
#     analyses.simwe(scanned_elev=scanned_elev, depth='depth', rain_value=300,
#                    niterations=4, tools=tools)
#
#
# def run_erosion(scanned_elev, tools, **kwargs):
#     analyses.erosion(scanned_elev=scanned_elev, rain_value=200, depth='depth',
#                      detachment_coeff=0.001, transport_coeff=0.01, shear_stress=0,
#                      sediment_flux='flux', erosion_deposition='erdep',
#                      niterations=4, tools=tools)

# def run_geomorphon(scanned_elev, tools, **kwargs):
#     analyses.geomorphon(scanned_elev, new='geomorphon', search=22, skip=12,
#                         flat=1, dist=0, tools=tools)

# def run_slope_aspect(scanned_elev, tools, **kwargs):
#     analyses.slope_aspect(scanned_elev=scanned_elev, slope='slope',
#                           aspect='aspect', tools=tools)

#
# def run_usped(scanned_elev, tools, **kwargs):
#     analyses.flowacc(scanned_elev, new='flowacc', tools=tools)
#     analyses.usped(scanned_elev, k_factor='soils_Kfactor',
#                    c_factor='cfactorbare_1m', flowacc='flowacc',
#                    slope='slope', aspect='aspect', new='erdep', tools=tools)

# def run_change_detection(scanned_elev, env, tools, **kwargs):
#     # trim region to avoid detecting differences on the edge
#     with RegionManager(n='n-20', s='s+20', e='e-20', w='w+20', env=env):
#         analyses.change_detection(before='scan_saved', after=scanned_elev,
#                                   change='change', height_threshold=[10, 30],
#                                   cells_threshold=[7, 100], add=True,
#                                   max_detected=6, debug=False, tools=tools)
#
# def run_trail(real_elev, scanned_elev, tools, **kwargs):
#     analyses.trails_combinations(real_elev, friction='friction',
#                                  walk_coeff=[0.72, 6.0, 1.9998, -1.9998],
#                                  _lambda=.5, slope_factor=-.8125,
#                                  walk='walk_result', walking_dir='walkdir_result',
#                                  points='change', raster_route='route_result',
#                                  vector_routes='route_result', mask=None,
#                                  tools=tools)
#     analyses.trail_salesman(trails='route_result', points='change',
#                             output='route_salesman', tools=tools)

# def run_viewshed(real_elev, scanned_elev, tools, **kwargs):
#     analyses.viewshed(real_elev, output='viewshed', obs_elev=1.75,
#                       vector='change', visible_color='green',
#                       invisible_color='red', tools=tools)

# def run_colors(scanned_elev, scanned_color, tools, **kwargs):
#     if scanned_color:
#         # need training phase, see Analyses tab
#         analyses.classify_colors(new='patches', group=scanned_color,
#                                  compactness=2, threshold=0.3, minsize=10,
#                                  useSuperPixels=False, tools=tools)
