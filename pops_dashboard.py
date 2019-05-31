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
        gscript.run_command('g.proj', 'epsg=4326', location=self._temp_location)
        gisrc, env = self._get_gisrc_environment()
        self._tmpgisrc = gisrc
        self._env = env
        self._tmp_out_file = gscript.tempfile(False)
        self._tmp_vect_file = 'tmp_vect_' + gscript.tempfile(False)
        self._tmp_rast_file = 'tmp_rast_' + gscript.tempfile(False)

    def set_root_URL(self, url):
        self._root = url

    def set_run_params(self, params):
        self._run = params

    def set_management_polygons(self, management):
        geojson = self.vector_to_geojson(management)
        self._run['management_polygons'] = geojson

    def upload_run(self):
        try:
            res = requests.post(self._root + 'run/', data=self._run)
            res.raise_for_status()
            self.run_id = res.json()['id']
        except requests.exceptions.HTTPError:
            return None

    # TODO
    def upload_results(self, year, raster):
        results = process_for_dashboard(year, raster)
        results['spread_map'] = self.raster_to_geojson(raster)

    def raster_to_geojson(self, raster):
        env = get_environment(raster=raster)
        gscript.mapcalc("{n} = if({r} == 0, null(), {r})".format(n=self._tmp_rast_file,
                        r=raster), overwrite=True, env=env)
        gscript.run_command('r.to.vect', flags='vt', input=self._tmp_rast_file,
                            output=self._tmp_vect_file, type='area', env=env)
        self.vector_to_geojson(self._tmp_vect_file)

    def vector_to_geojson(self, vector):
        gscript.run_command('v.proj', env=self._env) # TODO
        gscript.run_command('v.out.ogr', input=vector, output=self._tmp_out_file,
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
        tmp_gisrc_file = gscript.tempfile()
        with open(tmp_gisrc_file, 'w') as f:
            f.write('MAPSET: {mapset}\n'.format(mapset='PERMANENT'))
            f.write('GISDBASE: {g}\n'.format(g=env['GISDBASE']))
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
#    env = get_environment(raster=raster)
    data = gscript.parse_command('r.univar', map=raster, flags='gr')
    # TODO: finish number_infected, infected_area
    return result


def main():
    dashboard = PoPSDashboard()
    dashboard.set_root_URL('http://popsmodel.org/api/')
    dashboard.close()


if __name__ == '__main__':
    main()
