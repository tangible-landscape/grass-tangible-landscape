# -*- coding: utf-8 -*-
"""
Created on Wed Aug 23 09:29:18 2017

@author: anna
"""
import os
import shutil
import json
import requests

import grass.script as gscript

from tangible_utils import get_environment


class PoPSDashboard:
    def __init__(self):
        self._root = None
        self._run = {}
        self._run_id = None
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

    def set_run_params(self, params):
        self._run = params

    def set_management_polygons(self, management):
        geojson = self.vector_to_proj_geojson(management, 'treatment')
        self._run['management_polygons'] = geojson

    def upload_run(self):
        try:
            res = requests.post(self._root + 'run/', data=self._run)
            res.raise_for_status()
            self.run_id = res.json()['id']
        except requests.exceptions.HTTPError:
            return None

    def upload_results(self, year, raster):
        env = get_environment(raster=raster)
        gscript.mapcalc("{n} = if({r} == 0, null(), {r})".format(n=self._tmp_rast_file,
                        r=raster), env=env)
        results = process_for_dashboard(self._run_id, year, self._tmp_rast_file)
        results['spread_map'] = self.raster_to_proj_geojson(self._tmp_rast_file, env)
        try:
            res = requests.post(self._root + 'output/', data=results)
            res.raise_for_status()
            self.run_id = res.json()['id']
        except requests.exceptions.HTTPError:
            return None

    def raster_to_proj_geojson(self, raster, env):
        gscript.run_command('r.to.vect', input=raster,
                            output=self._tmp_vect_file, type='area', column='outputs', env=env)
        self.vector_to_proj_geojson(self._tmp_vect_file, 'output')

    def vector_to_proj_geojson(self, vector, name):
        genv = gscript.gisenv()
        gscript.run_command('v.proj', location=genv['LOCATION_NAME'], quiet=True,
                            mapset=genv['MAPSET'], input=vector, output=name, env=self._env)
        gscript.run_command('v.out.ogr', input=name, flags='sm', output=self._tmp_out_file,
                            format_='GeoJSON', quiet=True, overwrite=True,
                            env=self._env)
        with open(self._tmp_out_file) as f:
            j = json.load(f)
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



def process_for_dashboard(id_, year, raster):
    result = {'run': id_, 'years': year}
    data = gscript.parse_command('r.univar', map=raster, flags='gr')
    info = gscript.raster_info(raster)
    result['infected_area'] = int(data['n']) * info['nsres'] * info['ewres']
    result['number_infected'] = int(data['sum'])

    return result


def main():
    dashboard = PoPSDashboard()
    dashboard.set_root_URL('https://popsmodel.org/api/')
    
    dashboard.set_run_params(params={"name": "testTLconn", "reproductive_rate": 4,
                                     "distance_scale": 20, "cost_per_hectare": 1,
                                     "efficacy": 1, "session": 1})

    dashboard.set_management_polygons('treatments__tmpevent__player__53')
    dashboard.upload_run()
    dashboard.upload_results(2017, 'tmpevent__player__14_0__2021_12_31')
    dashboard.close()


if __name__ == '__main__':
    main()
