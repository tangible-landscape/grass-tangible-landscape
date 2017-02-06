# -*- coding: utf-8 -*-
"""
@brief utils

This program is free software under the GNU General Public License
(>=v2). Read the file COPYING that comes with GRASS for details.

@author: Anna Petrasova (akratoc@ncsu.edu)
"""
import os
import shutil
import imp
import traceback

import grass.script as gscript
from grass.exceptions import CalledModuleError, ScriptError

import wx
import wx.lib.newevent
updateGUIEvt, EVT_UPDATE_GUI = wx.lib.newevent.NewCommandEvent()
addLayers, EVT_ADD_LAYERS = wx.lib.newevent.NewEvent()
removeLayers, EVT_REMOVE_LAYERS = wx.lib.newevent.NewEvent()
checkLayers, EVT_CHECK_LAYERS = wx.lib.newevent.NewEvent()


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
    env['GRASS_REGION'] = gscript.region_env(**kwargs)
    return env


def remove_vector(name, deleteTable=False):
    """Helper function to workaround problem with deleting vectors"""
    gisenv = gscript.gisenv()
    path_to_vector = os.path.join(gisenv['GISDBASE'], gisenv['LOCATION_NAME'], gisenv['MAPSET'], 'vector', name)
    if deleteTable:
        try:
            gscript.run_command('db.droptable', table=name, flags='f')
        except CalledModuleError:
            pass
    if os.path.exists(path_to_vector):
        try:
            shutil.rmtree(path_to_vector)
        except StandardError:
            pass


def run_analyses(settings, analysesFile, update, giface, eventHandler, scanFilter, **kwargs):
    """Runs all functions in specified Python file which start with 'run_'.
    The Python file is reloaded every time"""

    scan_params = settings['tangible']['scan']
    if scanFilter['filter']:
        info = gscript.raster_info(scan_params['scan_name'] + 'tmp')
        if scanFilter['debug']:
            print info['max'] - info['min']
        threshold = scanFilter['threshold']
        if info['max'] - info['min'] > threshold:
            scanFilter['counter'] += 1
            return
    try:
        gscript.run_command('g.copy', raster=[scan_params['scan_name'] + 'tmp', scan_params['scan_name']], overwrite=True, quiet=True)
    except CalledModuleError:
        print 'error copying scanned data from temporary name'
        return
    env = get_environment(rast=scan_params['scan_name'])
    if not analysesFile or not os.path.exists(analysesFile):
        return
    # run analyses
    try:
        myanalyses = imp.load_source('myanalyses', analysesFile)
    except StandardError as e:
        print e
        return

    functions = [func for func in dir(myanalyses) \
        if (func.startswith('run_') and func != 'run_command') or func.startswith('drawing_')]
    for func in functions:
        exec('del myanalyses.' + func)
    try:
        myanalyses = imp.load_source('myanalyses', analysesFile)
    except StandardError as e:
        print e
        return
    # drawing needs different parameters
    # functions postprocessing drawing results start with 'drawing'
    # functions postprocessing scanning results start with 'run'

    if settings['tangible']['drawing']['active']:
        functions = [func for func in dir(myanalyses) if func.startswith('drawing_')]
        for func in functions:
            try:
                exec('myanalyses.' + func + "(real_elev=scan_params['elevation'],"
                                            " scanned_elev=scan_params['scan_name'],"
                                            " zexag=scan_params['zexag'],"
                                            " draw_vector=settings['tangible']['drawing']['name'],"
                                            " draw_vector_append=settings['tangible']['drawing']['append'],"
                                            " draw_vector_append_name=settings['tangible']['drawing']['appendName'],"
                                            " giface=giface, update=update,"
                                            " eventHandler=eventHandler, env=env, **kwargs)")
            except (CalledModuleError, StandardError, ScriptError) as e:
                print traceback.print_exc()
    else:
        functions = [func for func in dir(myanalyses) if func.startswith('run_') and func != 'run_command']
        for func in functions:
            try:
                exec('myanalyses.' + func + "(real_elev=scan_params['elevation'],"
                                            " scanned_elev=scan_params['scan_name'],"
                                            " zexag=scan_params['zexag'],"
                                            " giface=giface, update=update,"
                                            " eventHandler=eventHandler, env=env, **kwargs)")
            except (CalledModuleError, StandardError, ScriptError) as e:
                print traceback.print_exc()
