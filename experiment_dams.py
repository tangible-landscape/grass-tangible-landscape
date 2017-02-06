# -*- coding: utf-8 -*-
"""
@brief experiment_dams

This program is free software under the GNU General Public License
(>=v2). Read the file COPYING that comes with GRASS for details.

@author: Anna Petrasova (akratoc@ncsu.edu)
"""
import grass.script as gscript
from datetime import datetime
from experiment import updateDisplay


def run_contours(real_elev, scanned_elev, eventHandler, env, **kwargs):
    gscript.run_command('r.contour', input=scanned_elev, output='flow_contours', step=20, flags='t', env=env)

def run_dams(real_elev, scanned_elev, eventHandler, env, **kwargs):
    # copy scan
    postfix = datetime.now().strftime('%H_%M_%S')
    prefix = 'dams'
    gscript.run_command('g.copy', raster=[scanned_elev, '{}_scan_{}'.format(prefix, postfix)], env=env)

    filter_depth = 1
    repeat = 2
    input_dem = scanned_elev
    new = 'transfer_dam'
    output = "tmp_filldir"
    output2 = "tmp_filldir2"
    tmp_dir = "tmp_dir"
    for i in range(repeat):
        gscript.run_command('r.fill.dir', input=input_dem, output=output, direction=tmp_dir, env=env)
        input_dem = output
    gscript.mapcalc('{new} = if({out} - {scan} > {depth}, {out} - {scan}, null())'.format(new=output2, out=output, scan=scanned_elev, depth=filter_depth), env=env)

    gscript.mapcalc('{} = if({}, 1, null())'.format(output, output2), env=env)
    gscript.run_command('r.clump', input=output, output='clumps', env=env)
    stats = gscript.read_command('r.stats', flags='cn', input='clumps', sort='desc', env=env).strip().splitlines()
    if len(stats) > 0 and stats[0]:
        cats = []
        for stat in stats:
            if float(stat.split()[1]) > 100: # larger than specified number of cells
                cat, value = stat.split()
                cats.append(cat)
        if cats:
            expression = '{new} = if(('.format(new=new)
            for i, cat in enumerate(cats):
                if i != 0:
                    expression += ' || '
                expression += '{clump} == {val}'.format(clump='clumps', val=cat)
            expression += '), {}, null())'.format(output2)
            gscript.run_command('r.mapcalc', overwrite=True, env=env, expression=expression)
        else:
            gscript.mapcalc('{} = null()'.format(new), env=env)
            event = updateDisplay(value=0)
            eventHandler.postEvent(receiver=eventHandler.experiment_panel, event=event)
            return
        colors = ['0 179:235:243', '10 46:132:223', '20 11:11:147', '100 11:11:50']
        gscript.write_command('r.colors', map=new, rules='-', stdin='\n'.join(colors), env=env)
        data = gscript.parse_command('r.univar', map=new, flags='g', env=env)
        reg = gscript.parse_command('g.region', flags='pg', env=env)
        volume = float(data['sum']) * float(reg['nsres']) * float(reg['ewres'])
        event = updateDisplay(value=int(volume /100000))
    else:
        gscript.mapcalc('{} = null()'.format(new), env=env)
        event = updateDisplay(value=0)
    # update profile
    eventHandler.postEvent(receiver=eventHandler.experiment_panel, event=event)

    # copy results
    gscript.run_command('g.copy', raster=[new, '{}_dams_{}'.format(prefix, postfix)], env=env)
