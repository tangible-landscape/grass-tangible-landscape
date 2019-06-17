# -*- coding: utf-8 -*-
"""
Created on Wed Aug 23 09:29:18 2017

@author: anna
"""
import os
import shutil
import requests
import tempfile
import threading

import grass.script as gscript

from tangible_utils import get_environment


class PoPSDashboard:
    def __init__(self):
        self._root = None
        self._run = {}
        self._run_id = None
        self._session_id = None
        self._create_new = False
        self._temp_location = 'temp_export_location_' + str(os.getpid())
        gscript.run_command('g.proj', epsg=4326, location=self._temp_location, quiet=True)
        gisrc, env = self._get_gisrc_environment()
        self._tmpgisrc = gisrc
        self._env = env
        self._tmp_out_file = gscript.tempfile(False)
        suffix = os.path.basename(gscript.tempfile(False)).replace('.', '_')
        self._tmp_vect_file = 'tmp_vect_' + suffix
        self._tmp_rast_file = 'tmp_rast_' + suffix

    def set_root_URL(self, url):
        self._root = url

    def set_session_id(self, sid):
        self._session_id = str(sid)

    def set_run_params(self, params):
        self._run = params

    def set_management_polygons(self, management):
        # TODO: add area/cost
        geojson = self._vector_to_proj_geojson(management, 'treatment')
        self._run['management_polygons'] = geojson

    def _compare_runs(self, run1, run2):
        same = True
        for each in run1.keys():
            if each in ('date_created', 'status', 'id',
                        'management_polygons', 'management_cost', 'management_area'):
                continue
            try:
                if run1[each] != run2[each]:
                    same = False
                    break
            except KeyError:
                return False
        return same

    def _get_run(self, run_id):
        try:
            res = requests.get(self._root + 'run/' + run_id + '/')
            res.raise_for_status()
            return res.json()
        except requests.exceptions.HTTPError:
            return None

    def _get_run_id(self):
        try:
            res = requests.get(self._root + 'session/' + self._session_id + '/')
            res.raise_for_status()
            run_id = str(res.json()['most_recent_run'])
            return run_id
        except requests.exceptions.HTTPError:
            return None

    def get_run_params(self):
        self._run_id = self._get_run_id()
        if not self._run_id:
            return None
        run = self._get_run(self._run_id)
        if self._compare_runs(run, self._run):
            self._create_new = True
        else:
            self._create_new = False
        self._run = self._get_run(self._run_id)
        return self._run

    def update_run(self):
        try:
            if self._create_new:
                res = requests.post(self._root + 'run/', data=self._run)
            else:
                res = requests.put(self._root + 'run/' + self._run_id + '/', data=self._run)
            res.raise_for_status()
            self._run_id = str(res.json()['id'])
            return self._run_id
        except requests.exceptions.HTTPError:
            return None

    def upload_results(self, year, raster):
        env = get_environment(raster=raster)
        gscript.mapcalc("{n} = if({r} == 0, null(), {r})".format(n=self._tmp_rast_file,
                        r=raster), env=env)
        results = process_for_dashboard(self._run_id, year, self._tmp_rast_file)
        t = threading.Thread(target=raster_to_proj_geojson_thread, args=(self._tmp_rast_file, self._env, results, self._root))
        t.start()
        
    def run_done(self, success=True):
        self._run['status'] = 'SUCCESS' if success else 'FAILURE'
        try:
            res = requests.put(self._root + 'run/' + self._run_id + '/', data=self._run)
            res.raise_for_status()
        except requests.exceptions.HTTPError:
            return None

    def _raster_to_proj_geojson(self, raster, env):
        gscript.run_command('r.to.vect', input=raster, flags='vt',
                            output=self._tmp_vect_file, type='area', column='outputs', env=env)
        return self._vector_to_proj_geojson(self._tmp_vect_file, 'output')

    def _vector_to_proj_geojson(self, vector, name):
        genv = gscript.gisenv()
        gscript.run_command('v.proj', location=genv['LOCATION_NAME'], quiet=True,
                            mapset=genv['MAPSET'], input=vector, output=name, overwrite=True, env=self._env)
        gscript.try_remove(self._tmp_out_file)
        gscript.run_command('v.out.ogr', input=name, flags='sm', output=self._tmp_out_file,
                            format_='GeoJSON', lco="COORDINATE_PRECISION=4", quiet=True, overwrite=True,
                            env=self._env)
        print self._tmp_out_file
        with open(self._tmp_out_file) as f:
            j = f.read()
        return j

    def _get_gisrc_environment(self):
        """Creates environment to be passed in run_command for example.
        Returns tuple with temporary file path and the environment. The user
        of this function is responsile for deleting the file."""
        env = os.environ.copy()
        genv = gscript.gisenv()
        tmp_gisrc_file = gscript.tempfile()
        with open(tmp_gisrc_file, 'w') as f:
            f.write('MAPSET: {mapset}\n'.format(mapset='PERMANENT'))
            f.write('GISDBASE: {g}\n'.format(g=genv['GISDBASE']))
            f.write('LOCATION_NAME: {l}\n'.format(l=self._temp_location))
            f.write('GUI: text\n')
        env['GISRC'] = tmp_gisrc_file
        return tmp_gisrc_file, env

    def close(self):
        path_to_location = os.path.join(gscript.gisenv()['GISDBASE'], self._temp_location)
        shutil.rmtree(path_to_location)
        os.remove(self._tmpgisrc)
        gscript.run_command('g.remove', type='vector', name=self._tmp_vect_file, flags='f', quiet=True)
        gscript.run_command('g.remove', type='raster', name=self._tmp_rast_file, flags='f', quiet=True)


def raster_to_proj_geojson_thread(raster, gisrcenv, results, root):
    tempdir = tempfile.mkdtemp()
    tmp_layer1 = os.path.basename(tempdir) + '1'
    tmp_layer2 = os.path.basename(tempdir) + '2'
    tmp_file = os.path.join(tempdir, 'out.json')
    
    env = get_environment(raster=raster)
    gscript.run_command('r.to.vect', input=raster, flags='v',
                        output=tmp_layer1, type='area', column='outputs', env=env)
    genv = gscript.gisenv()
    gscript.run_command('v.proj', location=genv['LOCATION_NAME'], quiet=True,
                        mapset=genv['MAPSET'], input=tmp_layer1, output=tmp_layer2, overwrite=True, env=gisrcenv)
    gscript.run_command('v.db.addcolumn', map=tmp_layer2, columns="outputs integer", quiet=True, env=gisrcenv)
    gscript.run_command('v.db.update', map=tmp_layer2, column='outputs', query_column='cat', quiet=True, env=gisrcenv)
    gscript.run_command('v.out.ogr', input=tmp_layer2, flags='sm', output=tmp_file,
                        format_='GeoJSON', lco="COORDINATE_PRECISION=4", quiet=True, overwrite=True,
                        env=gisrcenv)
    with open(tmp_file) as f:
        j = f.read()
        results['spread_map'] = j
        with open('/tmp/data.json', 'w') as f:
            f.write(str(results))
        shutil.rmtree(tempdir)
        gscript.run_command('g.remove', name=[tmp_layer1, tmp_layer2], quiet=True, flags='f', type=['raster', 'vector'])
        try:
            res = requests.post(root + 'output/', data=results)
            res.raise_for_status()

            out_id = res.json()['id']
            print 'out_id ' + str(out_id)
            return out_id
        except requests.exceptions.HTTPError, e:
            print e
            try:
                print res.json()
            except:
                print 'no json'
            return None
        


def process_for_dashboard(id_, year, raster):
    result = {'run': id_, 'years': year}
    data = gscript.parse_command('r.univar', map=raster, flags='gr')
    info = gscript.raster_info(raster)
    result['infected_area'] = int(data['n']) * info['nsres'] * info['ewres'] / 10000.
    result['number_infected'] = int(data['sum'])

    return result


def main():
    dashboard = PoPSDashboard()
    dashboard.set_root_URL('https://popsmodel.org/api/')
    dashboard.set_session_id(15)
    run = dashboard.get_run_params()
    print run['id']
#    dashboard.set_run_params(params={"name": "testTLconn3", "reproductive_rate": 4,
#                                     "distance_scale": 20, "cost_per_hectare": 1,
#                                     "efficacy": 1, "session": 1})

    dashboard.set_management_polygons('treatments__tmpevent__player__7')
    if dashboard.update_run():
        out_id = dashboard.upload_results(2021, 'tmpevent__player__7_0__2021_12_31')
        if out_id:
            dashboard.run_done()
        



if __name__ == '__main__':
    main()
