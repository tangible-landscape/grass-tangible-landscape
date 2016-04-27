# -*- coding: utf-8 -*-
"""
@brief utils

This program is free software under the GNU General Public License
(>=v2). Read the file COPYING that comes with GRASS for details.

@author: Anna Petrasova (akratoc@ncsu.edu)
"""
import os
import uuid
import shutil
import imp

from grass.script import core as gcore
from grass.exceptions import CalledModuleError, ScriptError


def get_environment(**kwargs):
    """!Returns environment for running modules.
    All modules for which region is important should
    pass this environment into run_command or similar.

    @param tmp_regions a list of temporary regions
    @param kwargs arguments for g.region

    @return environment as a dictionary
    """
    env = os.environ.copy()
    env['GRASS_OVERWRITE'] = '1'
    env['GRASS_VERBOSE'] = '0'
    env['GRASS_MESSAGE_FORMAT'] = 'standard'
    env['GRASS_REGION'] = gcore.region_env(**kwargs)
    return env


def remove_vector(name, deleteTable=False):
    """Helper function to workaround problem with deleting vectors"""
    gisenv = gcore.gisenv()
    path_to_vector = os.path.join(gisenv['GISDBASE'], gisenv['LOCATION_NAME'], gisenv['MAPSET'], 'vector', name)
    if deleteTable:
        try:
            gcore.run_command('db.droptable', table=name, flags='f')
        except CalledModuleError:
            pass
    if os.path.exists(path_to_vector):
        try:
            shutil.rmtree(path_to_vector)
        except StandardError:
            pass


def run_analyses(scan_params, analysesFile, **kwargs):
    """Runs all functions in specified Python file which start with 'run_'.
    The Python file is reloaded every time"""
    if not analysesFile or not os.path.exists(analysesFile):
        return

    env = get_environment(rast=scan_params['scan_name'])
    # run analyses
    try:
        myanalyses = imp.load_source('myanalyses', analysesFile)
    except StandardError as e:
        print e
        return
    functions = [func for func in dir(myanalyses) if func.startswith('run_') and func != 'run_command']
    for func in functions:
        exec('del myanalyses.' + func)
    try:
        myanalyses = imp.load_source('myanalyses', analysesFile)
    except StandardError as e:
        print e
        return
    functions = [func for func in dir(myanalyses) if func.startswith('run_') and func != 'run_command']
    for func in functions:
        try:
            exec('myanalyses.' + func + "(real_elev=scan_params['elevation'],"
                                        " scanned_elev=scan_params['scan_name'],"
                                        " zexag=scan_params['zexag'], env=env, **kwargs)")
        except StandardError as e:
            print e
