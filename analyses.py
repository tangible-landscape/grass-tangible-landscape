# -*- coding: utf-8 -*-
"""
@brief Available analyses (wrapper around GRASS modules or chains of tools)

This program is free software under the GNU General Public License
(>=v2). Read the file COPYING that comes with GRASS for details.

@author: Anna Petrasova (akratoc@ncsu.edu)
"""
import io
import os
import uuid
from math import sqrt

import grass.script as gs
from grass.tools import Tools, ToolError

from tangible_utils import remove_vector


def difference_scaled(real_elev, scanned_elev, new, env=None, tools=None):
    """!Computes difference of original and scanned (scan - orig).
    Uses regression for automatic scaling"""
    tools = tools or Tools(env=env)
    regression = "regression"
    regression_params = tools.r_regression_line(
        format="json", mapx=scanned_elev, mapy=real_elev
    )
    tools.r_mapcalc(
        expression="{regression} = {a} + {b} * {before}".format(
            a=regression_params["a"],
            b=regression_params["b"],
            before=scanned_elev,
            regression=regression,
        ),
    )
    tools.r_mapcalc(
        expression="{difference} = {regression} - {after}".format(
            regression=regression, after=real_elev, difference=new
        ),
    )
    tools.r_colors(map=new, color="differences")


def difference(real_elev, scanned_elev, new, zexag=1, env=None, tools=None):
    """Compute difference and set color table using standard deviations"""
    tools = tools or Tools(env=env)
    tmp = "tmp_resampled"
    tools.r_resamp_interp(input=real_elev, output=tmp, method="bilinear")
    tools.r_mapcalc(expression=f"{new} = {tmp} - {scanned_elev}")
    univar = tools.r_univar(format="json", map=real_elev)
    std1 = zexag * univar["stddev"]
    std2 = zexag * 2 * std1
    std3 = zexag * 3 * std1
    rules = [
        "-1000000 black",
        f"-{std3} black",
        f"-{std2} 202:000:032",
        f"-{std1} 244:165:130",
        "0 247:247:247",
        f"{std1} 146:197:222",
        f"{std2} 5:113:176",
        f"{std3} black",
        "1000000 black",
    ]
    tools.r_colors(map=new, rules=io.StringIO("\n".join(rules)))


def match_scan(base, scan, matched, env=None, tools=None):
    """Vertically match scan to base using linear regression"""
    tools = tools or Tools(env=env)
    coeff = tools.r_regression_line(mapx=scan, mapy=base, format="json")
    tools.r_mapcalc(
        expression="{matched} = {a} + {b} * {scan}".format(
            matched=matched, scan=scan, a=coeff["a"], b=coeff["b"]
        ),
    )


def rlake(scanned_elev, new, base, seed, level, env=None, tools=None, **kwargs):
    tools = tools or Tools(env=env)
    suffix = str(uuid.uuid4()).replace("-", "")[:5]
    match = "tmp_match" + suffix
    params = {}
    if isinstance(seed, list):
        params["coordinates"] = ",".join(str(each) for each in seed)
    else:
        params["seed"] = seed
    match_scan(base=base, scan=scanned_elev, matched=match, tools=tools)
    tools.r_lake(elevation=match, water_level=level, lake=new, **params)
    tools.g_remove(flags="f", type="raster", name=[match])


def flowacc(scanned_elev, new, env=None, tools=None):
    tools = tools or Tools(env=env)
    tools.r_flow(elevation=scanned_elev, flowaccumulation=new)


def slope(scanned_elev, new, env=None, tools=None):
    tools = tools or Tools(env=env)
    tools.r_slope_aspect(elevation=scanned_elev, slope=new)


def aspect(scanned_elev, new, env=None, tools=None):
    tools = tools or Tools(env=env)
    tools.r_slope_aspect(elevation=scanned_elev, aspect=new)


def slope_aspect(scanned_elev, slope, aspect, env=None, tools=None):
    tools = tools or Tools(env=env)
    tools.r_slope_aspect(elevation=scanned_elev, aspect=aspect, slope=slope)
    tools.r_colors(map=aspect, color="aspectcolr")


def shaded_relief(scanned_elev, new, zscale=10, env=None, tools=None):
    tools = tools or Tools(env=env)
    tools.r_shaded_relief(input=scanned_elev, output=new, zscale=zscale)


def simwe(
    scanned_elev,
    depth,
    rain_value,
    niterations,
    slope=None,
    aspect=None,
    man=None,
    man_value=None,
    env=None,
    tools=None,
):
    tools = tools or Tools(env=env)
    suffix = str(uuid.uuid4()).replace("-", "")[:5]
    options = {}
    if slope:
        options["slope"] = slope
    if aspect:
        options["aspect"] = aspect
    tools.r_slope_aspect(
        elevation=scanned_elev,
        dx="dx_" + suffix,
        dy="dy" + suffix,
        **options,
    )
    simwe_options = {}
    if man:
        simwe_options["man"] = man
    elif man_value:
        simwe_options["man_value"] = man_value
    tools.r_sim_water(
        elevation=scanned_elev,
        dx="dx_" + suffix,
        dy="dy" + suffix,
        rain_value=rain_value,
        depth=depth,
        nwalkers=10000,
        niterations=niterations,
        **simwe_options,
    )
    tools.g_remove(
        flags="f",
        type="raster",
        name=["dx_" + suffix, "dy" + suffix],
    )


def erosion(
    scanned_elev,
    rain_value,
    depth,
    detachment_coeff,
    transport_coeff,
    shear_stress,
    niterations,
    sediment_flux,
    erosion_deposition,
    slope=None,
    aspect=None,
    man=None,
    man_value=None,
    env=None,
    tools=None,
):
    tools = tools or Tools(env=env)
    suffix = str(uuid.uuid4()).replace("-", "")[:5]
    options = {}
    if slope:
        options["slope"] = slope
    if aspect:
        options["aspect"] = aspect
    dc, tc, tau = "dc" + suffix, "tc" + suffix, "tau" + suffix
    simwe_options = {}
    if man:
        simwe_options["man"] = man
    elif man_value:
        simwe_options["man_value"] = man_value
    tools.r_slope_aspect(
        elevation=scanned_elev,
        dx="dx_" + suffix,
        dy="dy" + suffix,
        **options,
    )
    tools.r_sim_water(
        elevation=scanned_elev,
        dx="dx_" + suffix,
        dy="dy" + suffix,
        rain_value=rain_value,
        depth=depth,
        nwalkers=10000,
        niterations=niterations,
        **simwe_options,
    )
    tools.r_mapcalc(
        expression="{dc} = {detachment_coeff}".format(
            dc=dc, detachment_coeff=detachment_coeff
        ),
    )
    tools.r_mapcalc(
        expression="{tc} = {transport_coeff}".format(
            tc=tc, transport_coeff=transport_coeff
        ),
    )
    tools.r_mapcalc(
        expression="{tau} = {shear_stress}".format(tau=tau, shear_stress=shear_stress),
    )
    tools.r_sim_sediment(
        elevation=scanned_elev,
        dx="dx_" + suffix,
        dy="dy" + suffix,
        water_depth=depth,
        detachment_coeff=dc,
        transport_coeff=tc,
        shear_stress=tau,
        sediment_flux=sediment_flux,
        erosion_deposition=erosion_deposition,
        niterations=niterations,
        nwalkers=10000,
        **simwe_options,
    )
    tools.g_remove(
        flags="f",
        type="raster",
        name=[dc, tc, tau, "dx_" + suffix, "dy" + suffix],
    )


def max_curv(scanned_elev, new, size=15, zscale=5, env=None, tools=None):
    tools = tools or Tools(env=env)
    tools.r_param_scale(
        input=scanned_elev,
        output=new,
        size=size,
        param="maxic",
        zscale=zscale,
    )
    tools.r_colors(map=new, color="byr")


def landform(scanned_elev, new, size=25, zscale=1, env=None, tools=None):
    tools = tools or Tools(env=env)
    tools.r_param_scale(
        input=scanned_elev,
        output=new,
        size=size,
        param="feature",
        zscale=zscale,
    )


def geomorphon(
    scanned_elev, new, search=22, skip=12, flat=1, dist=0, env=None, tools=None
):
    tools = tools or Tools(env=env)
    tools.r_geomorphon(
        elevation=scanned_elev,
        forms=new,
        search=search,
        skip=skip,
        flat=flat,
        dist=dist,
    )


def usped(
    scanned_elev, k_factor, c_factor, flowacc, slope, aspect, new, env=None, tools=None
):
    """!Computes net erosion and deposition (USPED model)"""
    tools = tools or Tools(env=env)
    suffix = str(uuid.uuid4()).replace("-", "")[:5]
    sedflow = "sedflow_" + suffix
    qsx = "qsx_" + suffix
    qsxdx = "qsxdx_" + suffix
    qsy = "qsy_" + suffix
    qsydy = "qsydy_" + suffix
    slope_sm = "slope_sm" + suffix
    tools.r_neighbors(input=slope, output=slope_sm, size=5)
    tools.r_mapcalc(
        expression="{sedflow} = 270. * {k_factor} * {c_factor} * {flowacc} * sin({slope})".format(
            c_factor=c_factor,
            k_factor=k_factor,
            slope=slope_sm,
            flowacc=flowacc,
            sedflow=sedflow,
        ),
    )
    tools.r_mapcalc(
        expression="{qsx} = {sedflow} * cos({aspect})".format(
            sedflow=sedflow, aspect=aspect, qsx=qsx
        ),
    )
    tools.r_mapcalc(
        expression="{qsy} = {sedflow} * sin({aspect})".format(
            sedflow=sedflow, aspect=aspect, qsy=qsy
        ),
    )
    tools.r_slope_aspect(elevation=qsx, dx=qsxdx)
    tools.r_slope_aspect(elevation=qsy, dy=qsydy)
    tools.r_mapcalc(
        expression="{erdep} = {qsxdx} + {qsydy}".format(
            erdep=new, qsxdx=qsxdx, qsydy=qsydy
        ),
    )
    tools.r_colors(
        map=new,
        rules=io.StringIO(
            "-15000 100 0 100\n-100 magenta\n-10 red\n-1 orange\n-0.1 yellow\n0 200 255 200\n0.1 cyan\n1 aqua\n10 blue\n100 0 0 100\n18000 black"
        ),
    )

    tools.g_remove(
        flags="f",
        type="raster",
        name=[sedflow, qsx, qsxdx, qsy, qsydy, slope_sm],
    )


def depression(scanned_elev, new, filter_depth=0, repeat=2, env=None, tools=None):
    """Run r.fill.dir to compute depressions"""
    tools = tools or Tools(env=env)
    suffix = str(uuid.uuid4()).replace("-", "")[:5]
    input_dem = scanned_elev
    output = "tmp_filldir" + suffix
    tmp_dir = "tmp_dir" + suffix
    for i in range(repeat):
        tools.r_fill_dir(input=input_dem, output=output, direction=tmp_dir)
        input_dem = output
    tools.r_mapcalc(
        expression="{new} = if({out} - {scan} > {depth}, {out} - {scan}, null())".format(
            new=new, out=output, scan=scanned_elev, depth=filter_depth
        ),
    )
    tools.r_colors(map=new, rules=io.StringIO("0% aqua\n100% blue"))
    tools.g_remove(flags="f", type="raster", name=[output, tmp_dir])


def contours(scanned_elev, new, maxlevel=None, step=None, env=None, tools=None):
    tools = tools or Tools(env=env)
    name = "x" + str(uuid.uuid4()).replace("-", "")
    if not step:
        info = tools.r_info(map=scanned_elev, format="json")
        step = (info["max"] - info["min"]) / 12.0
    try:
        if maxlevel is None:
            tools.r_contour(
                input=scanned_elev,
                output=name,
                step=step,
                flags="t",
            )
        else:
            tools.r_contour(
                input=scanned_elev,
                output=name,
                step=step,
                maxlevel=maxlevel,
                flags="t",
            )
        tools.g_rename(vector=[name, new])
    except Exception:
        # catching exception when a vector is added to GUI in the same time
        pass
    except ToolError as e:
        tools.g_remove(flags="f", type="vector", name=[name])
        remove_vector(new, deleteTable=False)
        print(e)


def change_detection_area(
    before,
    after,
    change,
    height_threshold,
    filter_slope_threshold,
    add,
    env=None,
    tools=None,
):
    """Detects change in area. Result are areas with value
    equals the max difference between the scans as a positive value."""
    tools = tools or Tools(env=env)
    slope = "slope_tmp_get_change"
    before_after_regression = "before_after_regression_tmp"

    # slope is used to filter areas of change with high slope (edge of model)
    tools.r_slope_aspect(elevation=before, slope=slope)
    if add:
        after, before = before, after

    # regression
    reg_params = tools.r_regression_line(format="json", mapx=before, mapy=after)
    tools.r_mapcalc(
        expression="{before_after_regression} = {a} + {b} * {before}".format(
            a=reg_params["a"],
            b=reg_params["b"],
            before=before,
            before_after_regression=before_after_regression,
        ),
    )

    tools.r_mapcalc(
        expression="{change} = if({slope} < {filter_slope_threshold} && {before_after_regression} - {after} > {min_z_diff}, {before_after_regression} - {after}, null())".format(
            change=change,
            slope=slope,
            filter_slope_threshold=filter_slope_threshold,
            before_after_regression=before_after_regression,
            after=after,
            min_z_diff=height_threshold,
        ),
    )

    tools.g_remove(
        type="raster",
        name=["slope_tmp_get_change", "before_after_regression_tmp"],
        flags="f",
    )


def change_detection(
    before,
    after,
    change,
    height_threshold,
    cells_threshold,
    add,
    max_detected,
    debug,
    env=None,
    tools=None,
):
    tools = tools or Tools(env=env)
    diff_thr = "diff_thr_" + str(uuid.uuid4()).replace("-", "")
    diff_thr_clump = "diff_thr_clump_" + str(uuid.uuid4()).replace("-", "")
    coeff = tools.r_regression_line(mapx=after, mapy=before, format="json")
    tools.r_mapcalc(
        expression="diff = {a} + {b} * {after} - {before}".format(
            a=coeff["a"], b=coeff["b"], before=before, after=after
        ),
    )
    try:
        if add:
            tools.r_mapcalc(
                expression="{diff_thr} = if(({a} + {b} * {after} - {before}) > {thr1} &&"
                " ({a} + {b} * {after} - {before}) < {thr2}, 1, null())".format(
                    a=coeff["a"],
                    b=coeff["b"],
                    diff_thr=diff_thr,
                    after=after,
                    before=before,
                    thr1=height_threshold[0],
                    thr2=height_threshold[1],
                ),
            )
        else:
            tools.r_mapcalc(
                expression="{diff_thr} = if(({before} - {a} + {b} * {after}) > {thr}, 1, null())".format(
                    diff_thr=diff_thr,
                    a=coeff["a"],
                    b=coeff["b"],
                    after=after,
                    before=before,
                    thr=height_threshold,
                ),
            )

        tools.r_clump(input=diff_thr, output=diff_thr_clump)
        stats = tools.r_stats(
            flags="cn",
            input=diff_thr_clump,
            sort="desc",
            format="json",
        )
        if debug:
            stat_list = [
                f"Category {st['categories'][0]['category']}: {st['count']} cells"
                for st in stats
            ]
            print(f"DEBUG: {', '.join(stat_list)}")
        if len(stats) > 0 and stats[0]:
            cats = []
            found = 0
            for stat in stats:
                if found >= max_detected:
                    break
                if (
                    stat["count"] < cells_threshold[1]
                    and stat["count"] > cells_threshold[0]
                ):  # larger than specified number of cells
                    found += 1
                    cats.append(stat["categories"][0]["category"])
            if cats:
                rules = ["{c}:{c}:1".format(c=c) for c in cats]
                tools.r_recode(
                    input=diff_thr_clump,
                    output=change,
                    rules=io.StringIO("\n".join(rules)),
                )
                tools.r_volume(
                    flags="f",
                    input=change,
                    clump=diff_thr_clump,
                    centroids=change,
                )
            else:
                gs.warning("No change found!")
                tools.v_edit(map=change, tool="create")
        else:
            gs.warning("No change found!")
            tools.v_edit(map=change, tool="create")

        tools.g_remove(
            flags="f",
            type=["raster"],
            name=[diff_thr, diff_thr_clump],
        )
    except Exception:
        tools.g_remove(
            flags="f",
            type=["raster"],
            name=[diff_thr, diff_thr_clump],
        )


def drain(elevation, point, drain, conditioned, env=None, tools=None):
    tools = tools or Tools(env=env)
    data = tools.v_out_ascii(input=point, format="point").text
    if data:
        x, y, cat = data.split("|")
        if conditioned:
            tools.r_hydrodem(
                input=elevation,
                output=conditioned,
                mod=50,
                size=50,
                flags="a",
            )
            tools.r_drain(
                input=conditioned,
                output=drain,
                drain=drain,
                start_coordinates="{},{}".format(x, y),
            )
        else:
            tools.r_drain(
                input=elevation,
                output=drain,
                drain=drain,
                start_coordinates="{},{}".format(x, y),
            )
    else:
        tools.v_edit(map=drain, tool="create")


def trails_combinations(
    scanned_elev,
    friction,
    walk_coeff,
    _lambda,
    slope_factor,
    walk,
    walking_dir,
    points,
    raster_route,
    vector_routes,
    mask,
    env=None,
    tools=None,
):
    import itertools

    tools = tools or Tools(env=env)
    coordinates = tools.v_out_ascii(input=points, format="point", separator=",").text
    coords_list = []
    for coords in coordinates.split(os.linesep):
        coords_list.append(coords.split(",")[:2])

    combinations = itertools.combinations(coords_list, 2)
    combinations = [
        list(group) for k, group in itertools.groupby(combinations, key=lambda x: x[0])
    ]
    i = k = 0
    vector_routes_list = []

    walk_tmp = "walk_tmp"
    walk_dir_tmp = "walk_dir_tmp"
    raster_route_tmp = "raster_route_tmp"

    with gs.MaskManager(env=env):
        if mask:
            tools.r_mask(raster=mask)
        for points in combinations:
            i += 1
            point_from = ",".join(points[0][0])
            points_to = [",".join(pair[1]) for pair in points]
            vector_routes_list_drain = []
            for each in points_to:
                vector_route_tmp = "route_path_" + str(k)
                vector_routes_list_drain.append(vector_route_tmp)
                k += 1
            vector_routes_list.extend(vector_routes_list_drain)

            trail(
                scanned_elev,
                friction,
                walk_coeff,
                _lambda,
                slope_factor,
                walk_tmp,
                walk_dir_tmp,
                point_from,
                points_to,
                raster_route_tmp,
                vector_routes_list_drain,
                tools=tools,
            )
    tools.v_patch(
        input=vector_routes_list,
        output=vector_routes,
    )

    tools.g_remove(
        flags="f",
        type="raster",
        name=[walk_tmp, walk_dir_tmp, raster_route_tmp],
    )


# procedure for finding a trail in real-time
def trail(
    scanned_elev,
    friction,
    walk_coeff,
    _lambda,
    slope_factor,
    walk,
    walk_dir,
    point_from,
    points_to,
    raster_route,
    vector_routes,
    env=None,
    tools=None,
):
    tools = tools or Tools(env=env)
    tools.r_walk(
        flags="k",
        elevation=scanned_elev,
        friction=friction,
        output=walk,
        start_coordinates=point_from,
        outdir=walk_dir,
        stop_coordinates=points_to,
        walk_coeff=walk_coeff,
        _lambda=_lambda,
        slope_factor=slope_factor,
    )
    for i in range(len(points_to)):
        tools.r_drain(
            input=walk,
            direction=walk_dir,
            flags="d",
            drain=vector_routes[i],
            output=raster_route,
            start_coordinates=points_to[i],
        )


def trail_salesman(trails, points, output, env=None, tools=None):
    tools = tools or Tools(env=env)
    net_tmp = "net_tmp"
    tools.v_net(
        input=trails,
        points=points,
        output=net_tmp,
        operation="connect",
        threshold=10,
    )
    cats = tools.v_category(input=net_tmp, layer=2, option="print", format="json")
    tools.v_net_salesman(
        input=net_tmp,
        output=output,
        ccats=[cat["category"] for cat in cats],
        alayer=1,
        nlayer=2,
    )


def viewshed(
    scanned_elev,
    output,
    vector,
    visible_color,
    invisible_color,
    obs_elev=1.7,
    env=None,
    tools=None,
):
    tools = tools or Tools(env=env)
    coordinates = tools.v_out_ascii(input=vector, separator=",").text
    coordinate = None
    for line in coordinates.split(os.linesep):
        try:
            coordinate = [float(c) for c in line.split(",")[0:2]]
        except ValueError:  # no points in map
            pass
        break
    if coordinate:
        tools.r_viewshed(
            flags="b",
            input=scanned_elev,
            output=output,
            coordinates=coordinate,
            observer_elevation=obs_elev,
        )
        tools.r_null(map=output, null=0)
        tools.r_colors(
            map=output,
            rules=io.StringIO(
                "0 {invis}\n1 {vis}".format(vis=visible_color, invis=invisible_color)
            ),
        )


def polygons(points_map, output, env=None, tools=None):
    """Clusters markers together and creates polygons.
    Requires GRASS 7.1."""
    tools = tools or Tools(env=env)
    tmp_cluster = "tmp_cluster"
    tmp_hull = "tmp_hull"
    tools.v_cluster(
        flags="t",
        input=points_map,
        min=3,
        layer="3",
        output=tmp_cluster,
        method="optics",
    )
    cats = tools.v_category(input=tmp_cluster, layer="3", option="print", format="json")
    cats = [cat["category"] for cat in cats]
    cats_list = list(set(cats))
    cats_dict = dict([(x, cats.count(x)) for x in cats_list])
    for cat in cats_list:
        if cats_dict[cat] > 2:
            tools.v_hull(
                input=tmp_cluster,
                output=tmp_hull + "_%s" % cat,
                cats=cat,
                layer="3",
            )
        elif cats_dict[cat] == 2:
            points = tools.v_out_ascii(
                input=tmp_cluster,
                format="point",
                separator="space",
                layer="3",
                cats=cat,
            ).text.splitlines()
            ascii = "L 2 1\n" + points[0] + "\n" + points[1] + "\n" + "1 1"
            tools.v_in_ascii(
                format="standard",
                input=io.StringIO(ascii),
                flags="n",
                output=tmp_hull + "_%s" % cat,
            )
    tools.v_patch(
        input=[tmp_hull + "_%s" % cat for cat in cats_list],
        output=output,
    )
    tools.v_to_rast(
        input=output,
        output=output,
        type="area,line",
        use="val",
        value=1,
    )


def polylines(points_map, output, env=None, tools=None):
    """Cluster points and connect points by line in each cluster"""
    tools = tools or Tools(env=env)
    tmp_cluster = "tmp_cluster"
    tools.v_cluster(
        flags="t",
        input=points_map,
        min=3,
        layer="3",
        output=tmp_cluster,
        method="optics",
    )
    cats = tools.v_category(input=tmp_cluster, layer=3, option="print", format="json")
    cats = [cat["category"] for cat in cats]
    cats = list(set(cats))
    line = ""
    for cat in cats:
        point_list = []
        distances = {}
        points = tools.v_out_ascii(
            input=tmp_cluster,
            layer=3,
            type="point",
            cats=cat,
            format="point",
        ).text.split()
        for point in points:
            point = point.split("|")[:2]
            point_list.append((float(point[0]), float(point[1])))
        for i, point1 in enumerate(point_list[:-1]):
            for point2 in point_list[i + 1 :]:
                distances[(point1, point2)] = sqrt(
                    (point1[0] - point2[0]) * (point1[0] - point2[0])
                    + (point1[1] - point2[1]) * (point1[1] - point2[1])
                )
        ordered = sorted(distances.items(), key=lambda x: x[1])[: len(points) - 1]
        for key, value in ordered:
            line += "L 2 1\n"
            line += "{x} {y}\n".format(x=key[0][0], y=key[0][1])
            line += "{x} {y}\n".format(x=key[1][0], y=key[1][1])
            line += "1 {cat}\n\n".format(cat=cat)
    tools.v_in_ascii(
        input=io.StringIO(line),
        output=output,
        format="standard",
        flags="n",
    )
    tools.v_to_rast(input=output, output=output, type="line", use="cat")


def cross_section(scanned_elev, voxel, new, env=None, tools=None):
    tools = tools or Tools(env=env)
    tools.r3_cross_rast(
        input=voxel,
        elevation=scanned_elev,
        output=new,
    )
    tools.r_colors(map=new, raster_3d=voxel)


def subsurface_slice(
    points, voxel, slice_, axes, slice_line, units, offset, env=None, tools=None
):
    tools = tools or Tools(env=env)
    topo = tools.v_info(map=points, flags="t", format="json")
    if topo:
        if topo["points"] != 2:
            tools.r_mapcalc(expression=slice_ + " = null()")
            return

    coordinates = tools.v_out_ascii(input=points, format="point", separator=",").text
    coords_list = []
    i = 0
    for coords in coordinates.split(os.linesep):
        coords_list.extend(coords.split(",")[:2])
        i += 1
        if i >= 2:
            break
    if axes:
        tools.db_droptable(flags="f", table=axes)
    tools.r3_slice(
        input=voxel,
        output=slice_,
        coordinates=",".join(coords_list),
        axes=axes,
        slice_line=slice_line,
        units=units,
        offset=offset,
    )


def subsurface_borehole(
    points, voxel, new, size, offset, axes, unit, env=None, tools=None
):
    tools = tools or Tools(env=env)
    coordinates = tools.v_out_ascii(input=points, format="point", separator=",").text
    coords_list = []

    for coords in coordinates.split(os.linesep):
        coords_list.extend(coords.split(",")[:2])
    tools.r3_borehole(
        input=voxel,
        output=new,
        coordinates=",".join(coords_list),
        size=size,
        offset_size=offset,
        axes=axes,
        unit=unit,
    )


def classify_colors(
    new,
    group,
    compactness=2,
    threshold=0.3,
    minsize=10,
    useSuperPixels=True,
    env=None,
    tools=None,
):
    tools = tools or Tools(env=env)
    segment = "tmp_segment"
    segment_clump = "tmp_segment_clump"
    # we expect this name of signature
    signature = "signature"
    classification = "tmp_classification"
    filtered_classification = "tmp_filtered_classification"
    reject = "tmp_reject"
    if useSuperPixels:
        try:
            tools.i_superpixels_slic(
                input=group,
                output=segment,
                compactness=compactness,
                minsize=minsize,
            )
        except ToolError as e:
            print("i.superpixels.slic failed")
            print(e)
    else:
        tools.i_segment(
            group=group,
            output=segment,
            threshold=threshold,
            minsize=minsize,
        )
        tools.r_clump(input=segment, output=segment_clump)

    tools.i_smap(
        group=group,
        subgroup=group,
        signaturefile=signature,
        output=classification,
        goodness=reject,
    )
    percentile = tools.r_univar(flags="e", map=reject, format="json", percentile=90)[
        "percentiles"
    ][0]["value"]
    tools.r_mapcalc(
        expression="{new} = if({reject} < {thres}, {classif}, null())".format(
            new=filtered_classification,
            reject=reject,
            classif=classification,
            thres=percentile,
        ),
    )
    segments = segment if useSuperPixels else segment_clump
    tools.r_mode(base=segments, cover=filtered_classification, output=new)
