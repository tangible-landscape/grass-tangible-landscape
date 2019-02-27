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
import StringIO
import base64

import grass.script as gscript
from grass.exceptions import CalledModuleError, ScriptError

import wx
import wx.lib.newevent
updateGUIEvt, EVT_UPDATE_GUI = wx.lib.newevent.NewCommandEvent()
addLayers, EVT_ADD_LAYERS = wx.lib.newevent.NewEvent()
removeLayers, EVT_REMOVE_LAYERS = wx.lib.newevent.NewEvent()
checkLayers, EVT_CHECK_LAYERS = wx.lib.newevent.NewEvent()
selectLayers, EVT_SELECT_LAYERS = wx.lib.newevent.NewEvent()
changeLayer, EVT_CHANGE_LAYER = wx.lib.newevent.NewEvent()


def get_show_layer_icon():
    SHOW_LAYER_ICON = """iVBORw0KGgoAAAANSUhEUgAAABgAAAAYCAYAAADgdz34AAAABHNCSVQI
    CAgIfAhkiAAAAAlwSFlzAAAN1wAADdcBQiibeAAAABl0RVh0U29mdHdhcmUAd3d3Lmlua3NjYXB
    lLm9yZ5vuPBoAAAAYdEVYdEF1dGhvcgBSb2JlcnQgU3pjemVwYW5la19WsQgAAAAndEVYdERlc2
    NyaXB0aW9uAGh0dHA6Ly9yb2JlcnQuc3pjemVwYW5lay5wbJBZSGAAAAAYdEVYdENyZWF0aW9uI
    FRpbWUAMjAwOC0xMi0xMlguO78AAABSdEVYdENvcHlyaWdodABDQyBBdHRyaWJ1dGlvbi1TaGFy
    ZUFsaWtlIGh0dHA6Ly9jcmVhdGl2ZWNvbW1vbnMub3JnL2xpY2Vuc2VzL2J5LXNhLzMuMC9eg1q
    8AAADaUlEQVRIie2VX0xbVRzHv+e2vf23tvyxCFXblD8WbCFqcUJTzMrszLKMxCxA9MEMghozM8
    MDvGCikT0YfVg0ZDExc4tZYgIRE2UOxgKRJaSwZk7oBJy0WDBAgXKh3tveyu3xQduEUWaMmcbE7
    +P55vw+5/s99+QSSinup5j7Ov2fAMjvZRJCGPuTtcUy2U4FwNgopQyhNEYYxFKUiZEUjREZXb01
    OXl73xl338ETT9Uekgit/8OUCEhQYugM5TWzer0o8TzRpRSiTs4wupREdERGTZSSSkIIZRh8dtP
    n+34PoKmpSTYXXDhFGeYBgtQ3UzdujNC/ePsej0cejfEvU6AwX6ftHh0d3dmVwOFy5QXGx6MAYP
    V4VIWS5CwqNB2BXP0gVHkFKo1yOzw7eZ5bWZkIBALJ/UA1NTV6n8+3nbWi6urqIpu9suexCtvjB
    6udRQ+brep3P5/HMXcpft5MYnkzDiS4+K+x1cj22sJsaObbT2lsrTd92mzKAJ5raKh/2um88Epb
    q1mr0QAALg7P404UOFyZD51iB329fVhcjsB68Dg0BiNEMQlu5lqIC/vPDPT3f5INwKRjOcorPmg
    //XpmOACEIzzUKha3wgJCc9MwyH7B8g8TCE1+BQBQKlkYS2utHe1v9Lz40smrLpdLnRUgCArZAd
    0B5X4xBVHCF4NjGB4ZzepXORzq7rfffLaswn7N4XLlZa3o+ebmt7o6O7pKiq2KtJmuSK1iIWytZ
    U6eriieSKIsDzjpLQEA8DyPjz4+P8dtbS1tbGwu+X3jr2ZesoLSM++d/XBoZTUipdca6ywQOA4A
    oDEYYfe2wu5thcZg/D0Zx6GxzrIrjdFozBHFpDaeSKwolUq66yvyeDxyk9ny5elTrx1+tKyUBYC
    p4CYuDAehycmBWsUCAOKJJASOQ4u3GFXFuQCA+WBIPNtzbuy76am2gN8f3lNRZoEQcqL5he5n3K
    6W5sYTJpZlwSd20Hf9J4QjPADAXKBFY50FWpUclFJcvjK0PjA4eLH30qXOux/oHkBa9UeP2h4qM
    r1TbrM5vfWHSizmR8CybMbfiEYxcGVocToQuL0cibz/dX//SLY5+wLSKne7dZbc3Aa93uA26PUm
    Sqkk8AIfF8U7S8Efz/n9/vV77f9TwN/Vf/+H8z/g3wf8BtScfGRhgC1qAAAAAElFTkSuQmCC"""
    return wx.BitmapFromImage(wx.ImageFromStream(StringIO.StringIO(base64.b64decode(SHOW_LAYER_ICON))))

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
    scan_name = settings['tangible']['output']['scan']
    if scanFilter['filter']:
        try:
            info = gscript.raster_info(scan_name + 'tmp')
        except CalledModuleError:
            print 'error in r.info'
            return
        if scanFilter['debug']:
            try:
                print info['max'] - info['min']
            except TypeError:  # unsupported operand type(s) for -: 'NoneType' and 'NoneType'
                return
        threshold = scanFilter['threshold']
        if info['max'] - info['min'] > threshold:
            scanFilter['counter'] += 1
            return
    try:
        gscript.run_command('g.copy', raster=[scan_name + 'tmp', scan_name], overwrite=True, quiet=True)
    except CalledModuleError:
        print 'error copying scanned data from temporary name'
        return
    # workaround weird georeferencing
    # filters cases when extent and elev values are in inconsistent state
    # probably it reads it before the header is written
    try:
        info = gscript.raster_info(scan_name)
    except CalledModuleError:
        print 'error in r.info'
        return
    if (abs(info['north'] - info['south']) / (info['max'] - info['min'])) < 1:
        return
    env = get_environment(rast=scan_name)
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
    # color output
    color = None
    if settings['tangible']['output']['color']:
        color = settings['tangible']['output']['color_name']
    # blender path
    blender_path = None
    if settings['tangible']['output']['blender']:
        blender_path = settings['tangible']['output']['blender_path']
    # drawing needs different parameters
    # functions postprocessing drawing results start with 'drawing'
    # functions postprocessing scanning results start with 'run'

    if settings['tangible']['drawing']['active']:
        functions = [func for func in dir(myanalyses) if func.startswith('drawing_')]
        for func in functions:
            try:
                exec('myanalyses.' + func + "(real_elev=scan_params['elevation'],"
                                            " scanned_elev=scan_name,"
                                            " blender_path=blender_path,"
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
                                            " scanned_elev=scan_name,"
                                            " scanned_color=color,"
                                            " blender_path=blender_path,"
                                            " zexag=scan_params['zexag'],"
                                            " giface=giface, update=update,"
                                            " eventHandler=eventHandler, env=env, **kwargs)")
            except (CalledModuleError, StandardError, ScriptError) as e:
                print traceback.print_exc()
