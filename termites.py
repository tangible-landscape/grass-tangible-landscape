# -*- coding: utf-8 -*-
import os

import analyses
from tangible_utils import get_environment, remove_temp_regions

import grass.script as gscript


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

