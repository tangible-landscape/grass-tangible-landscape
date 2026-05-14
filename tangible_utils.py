# -*- coding: utf-8 -*-
"""
@brief utils

This program is free software under the GNU General Public License
(>=v2). Read the file COPYING that comes with GRASS for details.

@author: Anna Petrasova (akratoc@ncsu.edu)
"""
import os
import shutil
import importlib
import traceback

try:
    from StringIO import StringIO  # for Python 2
except ImportError:
    from io import BytesIO as StringIO  # for Python 3
import base64

from grass.script import gisenv, region_env, MaskManager, RegionManager
from grass.tools import Tools, ToolError
from grass.exceptions import CalledModuleError, ScriptError
from wxwrap import BitmapFromImage, ImageFromStream

import wx
import wx.lib.newevent

updateGUIEvt, EVT_UPDATE_GUI = wx.lib.newevent.NewCommandEvent()
addLayers, EVT_ADD_LAYERS = wx.lib.newevent.NewEvent()
removeLayers, EVT_REMOVE_LAYERS = wx.lib.newevent.NewEvent()
checkLayers, EVT_CHECK_LAYERS = wx.lib.newevent.NewEvent()
selectLayers, EVT_SELECT_LAYERS = wx.lib.newevent.NewEvent()
changeLayer, EVT_CHANGE_LAYER = wx.lib.newevent.NewEvent()


def get_TL_logo():
    logo = """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"""
    return BitmapFromImage(ImageFromStream(StringIO(base64.b64decode(logo))))


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
    return BitmapFromImage(ImageFromStream(StringIO(base64.b64decode(SHOW_LAYER_ICON))))


def load_source(modname, filename):
    """Replacement for imp.load_source"""
    loader = importlib.machinery.SourceFileLoader(modname, filename)
    spec = importlib.util.spec_from_file_location(modname, filename, loader=loader)
    module = importlib.util.module_from_spec(spec)
    # The module is always executed and not cached in sys.modules.
    # Uncomment the following line to cache the module.
    # sys.modules[module.__name__] = module
    loader.exec_module(module)
    return module


def get_environment(**kwargs):
    """!Returns environment for running modules.
    All modules for which region is important should
    pass this environment into run_command or similar.

    @param tmp_regions a list of temporary regions
    @param kwargs arguments for g.region

    @return environment as a dictionary
    """
    env = os.environ.copy()
    env["GRASS_OVERWRITE"] = "1"
    env["GRASS_VERBOSE"] = "0"
    env["GRASS_MESSAGE_FORMAT"] = "standard"
    region3d = False
    if "raster_3d" in kwargs:
        region3d = True
    env["GRASS_REGION"] = region_env(region3d=region3d, **kwargs)
    return env


def remove_vector(name, deleteTable=False):
    """Helper function to workaround problem with deleting vectors"""
    gis_env = gisenv()
    path_to_vector = os.path.join(
        gis_env["GISDBASE"], gis_env["LOCATION_NAME"], gis_env["MAPSET"], "vector", name
    )
    if deleteTable:
        try:
            Tools().db_droptable(table=name, flags="f")
        except ToolError:
            pass
    if os.path.exists(path_to_vector):
        try:
            shutil.rmtree(path_to_vector)
        except Exception:
            pass


def _dispatch_user_funcs(myanalyses, prefix, scan_name, base_env, call_kwargs, exclude=()):
    """Run each function in `myanalyses` whose name starts with `prefix`,
    each in its own isolated MaskManager / RegionManager / Tools(env=env) context.

    `tools` and `env` are injected into the per-call kwargs."""
    funcs = [
        f for f in dir(myanalyses)
        if f.startswith(prefix) and f not in exclude
    ]
    for func in funcs:
        env = base_env.copy()
        with (
            MaskManager(env=env),
            RegionManager(raster=scan_name, env=env),
            Tools(env=env, overwrite=True) as tools,
        ):
            try:
                getattr(myanalyses, func)(tools=tools, env=env, **call_kwargs)
            except (CalledModuleError, ToolError, Exception, ScriptError):
                traceback.print_exc()


def run_analyses(
    settings, analysesFile, update, giface, eventHandler, scanFilter, **kwargs
):
    """Runs all functions in specified Python file which start with 'run_'.
    The Python file is reloaded every time"""

    tools = Tools(overwrite=True, quiet=True)
    scan_params = settings["tangible"]["scan"]
    scan_name = settings["tangible"]["output"]["scan"]
    calibration = settings["tangible"]["output"]["calibrate"]
    calib_scan_name = settings["tangible"]["output"]["calibration_scan"]
    if calibration:
        scan_name = calib_scan_name
    if scanFilter["filter"]:
        try:
            info = tools.r_info(map=scan_name + "tmp", format="json")
        except ToolError:
            print("error in r.info")
            return
        if scanFilter["debug"]:
            try:
                print(info["max"] - info["min"])
            except (
                TypeError
            ):  # unsupported operand type(s) for -: 'NoneType' and 'NoneType'
                return
        threshold = scanFilter["threshold"]
        if info["max"] - info["min"] > threshold:
            scanFilter["counter"] += 1
            return
    try:
        tools.g_copy(raster=[scan_name + "tmp", scan_name])
    except ToolError:
        print("error copying scanned data from temporary name")
        return
    # workaround weird georeferencing
    # filters cases when extent and elev values are in inconsistent state
    # probably it reads it before the header is written
    try:
        info = tools.r_info(map=scan_name, format="json")
    except ToolError:
        print("error in r.info")
        return
    try:
        if (abs(info["north"] - info["south"]) / (info["max"] - info["min"])) < 1:
            return
    except ZeroDivisionError:
        return
    if not analysesFile or not os.path.exists(analysesFile):
        return
    # run analyses
    try:
        myanalyses = load_source("myanalyses", analysesFile)
    except Exception as e:
        print(e)
        return

    functions = [
        func
        for func in dir(myanalyses)
        if (func.startswith("run_") and func != "run_command")
        or func.startswith("drawing_")
        or func.startswith("calib_")
    ]
    for func in functions:
        exec("del myanalyses." + func)
    try:
        myanalyses = load_source("myanalyses", analysesFile)
    except Exception as e:
        print(e)
        return
    # color output
    color = None
    if settings["tangible"]["output"]["color"]:
        color = settings["tangible"]["output"]["color_name"]
    # blender path
    blender_path = None
    if settings["tangible"]["output"]["blender"]:
        blender_path = settings["tangible"]["output"]["blender_path"]
    # drawing needs different parameters
    # functions postprocessing drawing results start with 'drawing'
    # functions postprocessing scanning results start with 'run'
    base_env = os.environ.copy()
    base_env["GRASS_VERBOSE"] = "0"
    base_env["GRASS_MESSAGE_FORMAT"] = "standard"
    base_env["GRASS_OVERWRITE"] = "1"

    common_kwargs = {
        "real_elev": scan_params["elevation"],
        "scanned_elev": scan_name,
        "blender_path": blender_path,
        "zexag": scan_params["zexag"],
        "giface": giface,
        "update": update,
        "eventHandler": eventHandler,
        **kwargs,
    }

    if settings["tangible"]["drawing"]["active"]:
        drawing = settings["tangible"]["drawing"]
        _dispatch_user_funcs(myanalyses, "drawing_", scan_name, base_env, {
            **common_kwargs,
            "scanned_calib_elev": calib_scan_name,
            "draw_vector": drawing["name"],
            "draw_vector_append": drawing["append"],
            "draw_vector_append_name": drawing["appendName"],
        })
    elif calibration:
        _dispatch_user_funcs(myanalyses, "calib_", scan_name, base_env, {
            **common_kwargs,
            "scanned_calib_elev": scan_name,
            "scanned_color": color,
        })
    else:
        _dispatch_user_funcs(myanalyses, "run_", scan_name, base_env, {
            **common_kwargs,
            "scanned_calib_elev": calib_scan_name,
            "scanned_color": color,
        }, exclude={"run_command"})
