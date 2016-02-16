# -*- coding: utf-8 -*-
"""
This file serves as a control file with analyses
which are running in real-time. The name of the analyses
must start with 'run_'. The file has to be saved so that the change is applied.
"""

import analyses
from tangible_utils import get_environment, remove_temp_regions
import grass.script as gscript


#def run_contours(scanned_elev, env, **kwargs):
#    analyses.contours(scanned_elev=scanned_elev, new='contours_scanned', env=env, step=2)


def run_change_detection(scanned_elev, env, **kwargs):
    analyses.change_detection(before='scan', after=scanned_elev,
                              change='change', height_threshold=[10, 30], cells_threshold=[10, 200], add=True, max_detected=6, env=env)


def run_define_treatment(scanned_elev, env, **kwargs):
    # define input/output names
    before = 'scan_saved'
    matched = 'matched'
    UMCA = 'UMCA_den_100m'
    treatment = 'treatment'
    UMCA_changed = 'UMCA_changed'
    cost_UMCA_no_infection = 'cost_UMCA_no_infection'
    tmp_regions = []
    env2 = get_environment(tmp_regions, rast=scanned_elev, n='n-300', s='s+300', e='e-300', w='w+300')
    env3 = get_environment(tmp_regions, raster=UMCA)
    analyses.match_scan(base=before, scan=scanned_elev, matched=matched, env=env)
    analyses.change_detection(before=before, after=matched,
                              change='change', height_threshold=[40, 130],
                              cells_threshold=[3, 30], add=True, max_detected=12, env=env2)
    
    # POLYGONS
    treatment_shape = 'polygon'
    #treatment_shape = 'polyline'
    if treatment_shape == 'polygon':
        analyses.polygons(points_map='change', output=treatment, env=env3)
    else:
        analyses.polylines(points_map='change', output=treatment, env=env3)
    gscript.mapcalc(exp="{cost_UMCA_no_infection} = if(init_2000_cnt == 0, cost_UMCA, 0)".format(cost_UMCA_no_infection=cost_UMCA_no_infection), env=env3)
    gscript.mapcalc(exp="{UMCA_changed} = if(isnull({treatment}), {UMCA}, if(init_2000_cnt != 0, {UMCA}, 0))".format(UMCA=UMCA, treatment=treatment, UMCA_changed=UMCA_changed), env=env3)
    gscript.mapcalc(exp="cost_treated = if({treatment}, {cost_UMCA_no_infection})".format(treatment=treatment, cost_UMCA_no_infection=cost_UMCA_no_infection), env=env3)
    # for visualization with vectors
    if treatment_shape == 'polygon':
        gscript.run_command('r.clump', flags='d', input=treatment, output=UMCA_changed + 'clump', env=env3)
        gscript.run_command('r.stats.zonal', base=UMCA_changed + 'clump', cover=cost_UMCA_no_infection, output='cost_treated_zonal', method='sum', env=env3)
        gscript.mapcalc(exp="oaks_treated = if({treatment}, OAKS_den_100m)".format(treatment=treatment), env=env3)
        gscript.mapcalc(exp="umca_treated = if({treatment}, UMCA_den_100m)".format(treatment=treatment), env=env3)
    else:
        gscript.run_command('r.stats.zonal', base=treatment, cover=cost_UMCA_no_infection, output='cost_treated_zonal', method='sum', env=env3)
        gscript.mapcalc(exp="oaks_treated = if({treatment}, OAKS_den_100m)".format(treatment=treatment), env=env3)
        gscript.mapcalc(exp="umca_treated = if({treatment}, UMCA_den_100m)".format(treatment=treatment), env=env3)

    gscript.run_command('r.to.vect', input='cost_treated_zonal', output='cost_treated_zonal', column='cost', type='area', env=env3)
    dump = gscript.read_command('v.db.select', map='cost_treated_zonal', flags='c', env=env3).strip().split()
    uniques = set([line.split('|')[1] for line in dump])
    select_dict = {}
    toremove = []
    for unique in uniques:
        select_dict[unique] = []
        for line in dump:
            if line.split('|')[1] == unique:
                select_dict[unique].append(line.split('|')[0])
        toremove += select_dict[unique][1:]
    gscript.run_command('v.db.update', map='cost_treated_zonal', column='cost', value='NULL', where="cat IN ({all})".format(all=','.join(toremove)), env=env3)
        
    gscript.run_command('r.colors', map=UMCA_changed, raster=UMCA, env=env3)
    # vector for visulization of treatment size
    area = gscript.parse_command('r.univar', flags='g', map='cost_treated', env=env3)['n']
    gscript.write_command('v.in.ascii', input='-', stdin="-222651.76615|45933.4600897|%s ha" % area, 
                        columns="x double precision, y double precision, size varchar(20)", output='treatment_size_point', env=env3)
    remove_temp_regions(tmp_regions)
