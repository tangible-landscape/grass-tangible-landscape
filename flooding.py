import uuid

import analyses
import grass.script as gscript
from grass.exceptions import CalledModuleError

def run_flooding(real_elev, scanned_elev, new, env, round, **kwargs):
    seed = [703758.79476,11471.6200873]
    lake = "lake" + new + str(round)
    buildings = 'buildings'
    analyses.rlake(scanned_elev, new=lake, base=real_elev, env=env, seed=seed, level=3)
    lines = gscript.read_command('r.univar', flags='t', quiet=True, map=lake, zones=buildings, env=env).strip()
    cats = []
    if lines:
        lines = lines.splitlines()
        for line in lines[1:]:
            cats.append(line.split('|')[0])
    name = 'x' + str(uuid.uuid4()).replace('-', '')
    gscript.run_command('v.extract', input=buildings, output=name, flags='t', cats=','.join(cats), env=env)
    before = ''
    if round > 1:
        before = gscript.read_command('v.db.select', flags='c', map='score', columns='score', env=env).strip() + "   "
    gscript.run_command('v.db.update', map='score', layer=1, column='score', value=before + str(round) + ': ' + str(len(cats)), env=env)

    try:
        gscript.run_command('g.rename', raster=[lake, 'lake'], env=env)
        gscript.run_command('g.rename', vector=[name, 'flooded'], env=env)
        gscript.run_command('g.copy', raster=[scanned_elev, scanned_elev + new + str(round)], env=env)
    except CalledModuleError as e:
        gscript.run_command('g.remove', flags='f', type='vector', name=[name], env=env)
        print e