# -*- coding: utf-8 -*-
"""
@brief blender - export functions

This program is free software under the GNU General Public License
(>=v2). Read the file COPYING that comes with GRASS for details.

@author: Anna Petrasova (akratoc@ncsu.edu)
"""
import os
import shutil
import glob
from datetime import datetime

import grass.script as gscript
from grass.exceptions import CalledModuleError


def _removeShapefile(path, pattern):
    """Remove all files of a shapefile"""
    path = os.path.join(path, pattern)
    for f in glob.glob(path):
        os.remove(f)


def blender_send_file(name, path, text=""):
    """Save file with given name to path, can contain text"""
    if not (path and os.path.exists(path)):
        print("Blender path does not exist:\n{p}".format(p=path))
        return
    with open(os.path.join(path, name), "w") as f:
        f.write(text)
        f.close()


def blender_export_DEM(
    raster, path, name=None, tmp_path="/tmp", time_suffix=True, env=None
):
    """Export raster DEM under  certain name to be used by Blender"""
    if not (path and os.path.exists(path)):
        print("Blender path does not exist:\n{p}".format(p=path))
        return
    local = True
    if "server=" in path:
        local = False

    if time_suffix:
        time = datetime.now()
        suffix = "_{}_{}_{}".format(time.hour, time.minute, time.second)
    else:
        suffix = ""

    if not name:
        name = raster

    fullname = "{name}{suffix}.tif".format(name=name, suffix=suffix)

    if local:
        out = os.path.join(path, fullname)
    else:
        out = os.path.join(tmp_path, fullname)
    gscript.run_command(
        "r.out.gdal",
        flags="cf",
        input=raster,
        type="Float32",
        create="TFW=YES",
        out=out,
        quiet=True,
        env=env,
    )

    if not local:
        try:
            shutil.copyfile(out, os.path.join(path, fullname))
        except OSError as e:
            if e.errno == 95:
                pass


def blender_export_vector(
    vector,
    path,
    vtype,
    name=None,
    z=False,
    tmp_path="/tmp",
    time_suffix=False,
    env=None,
):
    """Export Shapfile of any vector type (point, line, area)"""
    if not (path and os.path.exists(path)):
        print("Blender path does not exist:\n{p}".format(p=path))
        return

    local = True
    if "server=" in path:
        local = False

    if time_suffix:
        time = datetime.now()
        suffix = "_{}_{}_{}".format(time.hour, time.minute, time.second)
    else:
        suffix = ""

    if not name:
        name = vector

    fullname = "{name}{suffix}.shp".format(name=name, suffix=suffix)
    if local:
        out = os.path.join(path, fullname)
    else:
        out = os.path.join(tmp_path, fullname)

    if os.path.exists(out):
        _removeShapefile(
            path if local else tmp_path,
            "{name}{suffix}.*".format(name=name, suffix=suffix),
        )
    try:
        params = {}
        if vtype == "line":
            params["lco"] = "SHPT=ARC"
        elif vtype == "area":
            params["lco"] = "SHPT=POLYGON"
        elif vtype == "point":
            params["lco"] = "SHPT=POINT"
        if z:
            params["lco"] += "Z"
        gscript.run_command(
            "v.out.ogr",
            input=vector,
            output=out,
            env=env,
            format="ESRI_Shapefile",
            **params
        )
    except CalledModuleError as e:
        print(e)

    if not local:
        for each in glob.glob(
            os.path.join(tmp_path, "{name}{suffix}.*".format(name=name, suffix=suffix))
        ):
            ext = each.split(".")[-1]
            try:
                shutil.copyfile(
                    each,
                    os.path.join(
                        path,
                        "{name}{suffix}.{ext}".format(
                            name=name, suffix=suffix, ext=ext
                        ),
                    ),
                )
            except OSError as e:
                if e.errno == 95:
                    pass


def blender_export_PNG(
    raster, path, name=None, tmp_path="/tmp", time_suffix=True, env=None
):
    """Export raster as PNG to be used by Blender, assumes 8bit"""
    if not (path and os.path.exists(path)):
        print("Blender path does not exist:\n{p}".format(p=path))
        return
    local = True
    if "server=" in path:
        local = False

    if time_suffix:
        time = datetime.now()
        suffix = "_{}_{}_{}".format(time.hour, time.minute, time.second)
    else:
        suffix = ""

    if not name:
        name = raster

    fullname = "{name}{suffix}.png".format(name=name, suffix=suffix)

    if local:
        out = os.path.join(path, fullname)
    else:
        out = os.path.join(tmp_path, fullname)
    gscript.run_command(
        "r.out.gdal", input=raster, format="PNG", out=out, quiet=True, env=env
    )

    if not local:
        try:
            shutil.copyfile(out, os.path.join(path, fullname))
        except OSError as e:
            if e.errno == 95:
                pass
