import os
import tempfile
import shutil
import uuid
import json

import grass.script as gs
from tangible_utils import get_environment
from pops_dashboard import dateFromString, dateToString


class Treatments:
    def __init__(self):
        self.model_settings = None
        self.tr_tl_name = None
        self.tr_registered_name = "tmp_registered_treatment"
        self.tr_registered_basename = "tmp_registered_treatment"
        self.treatments_for_model = []
        self._tr_registered = False
        self.tr_external_name = "external_treatment"
        self.tr_dashboard = "tmp_dashboard"
        self.tr_merged_name = None
        self.tr_external_json = None
        self.tr_dashboard_json = None
        self.do_resampling = False
        self.ignore_incoming = False
        self._env = None
        gs.run_command(
            "v.edit", map=self.tr_external_name, tool="create", overwrite=True, quiet=True
        )
        gs.run_command(
            "v.edit", map=self.tr_dashboard, tool="create", overwrite=True, quiet=True
        )

    def initialize(self, model_settings, study_area, workdir):
        self.model_settings = model_settings
        self.tr_tl_name = model_settings.pops["treatments"]
        self.workdir = workdir
        self.study_area = study_area
        # default env
        self._env = get_environment(raster=self.study_area)

    def reset_dashboard_treatment(self):
        self.tr_external_json = None
        self.tr_dashboard_json = None
        gs.run_command(
            "v.edit", map=self.tr_external_name, tool="create", env=self._env
        )
        gs.run_command(
            "v.edit", map=self.tr_dashboard, tool="create", env=self._env
        )

    # def register_treatment(self):
    #     """Register treatment from TL"""
    #     if not self._tr_registered:
    #         gs.run_command(
    #             "g.copy",
    #             raster=[self.tr_tl_name, self.tr_registered_name],
    #             env=self._env,
    #         )
    #         self._tr_registered = True
    #         return

    #     registered_info = gs.raster_info(self.tr_registered_name)
    #     new_info = gs.raster_info(self.tr_tl_name)
    #     if registered_info["nsres"] > new_info["nsres"]:
    #         align = self.tr_tl_name
    #     else:
    #         align = self.tr_registered_name

    #     if "region" in self.model_settings.pops:
    #         env = get_environment(
    #             region=self.model_settings.pops["region"], align=align
    #         )
    #     else:
    #         env = get_environment(raster=self.study_area, align=align)

    #     gs.run_command(
    #         "r.patch",
    #         input=[self.tr_registered_name, self.tr_tl_name],
    #         output=self.tr_registered_name,
    #         env=env,
    #     )
    #     self._tr_registered = True
    #     # TODO: send to dashboard

    def register_treatment(self, year, use_dashboard):
        """Register treatment from TL"""
        self.treatments_for_model = []
        tr_env = get_environment(raster=self.tr_tl_name)
        # convert to vector for sending to dashboard
        gs.run_command("r.to.vect",
                       input=self.tr_tl_name,
                       output=self.tr_tl_name,
                       type="area",
                       env=tr_env)
        gs.run_command(
            "v.to.db",
            map=self.tr_tl_name,
            option="area",
            columns="area",
            units="meters",
            env=tr_env,
        )
        # the rest is not needed with dashboard
        if use_dashboard:
            return
        # we assume only 1 treatment type in year
        # when we don't have dashboard
        name = f"{self.tr_registered_basename}__0"
        host = self.model_settings.model["host"]
        host = self.model_settings.model["host"]
        host_env = get_environment(raster=host)
        efficacy = self.model_settings.pops["efficacy"]
        need_resample = bool(
            "cell_treatment_proportion" in self.model_settings.pops
            and self.model_settings.pops["cell_treatment_proportion"]
        )
        if need_resample:
            tmp1 = "tmp_resampled"
            gs.run_command(
                "r.resamp.stats",
                input=self.tr_tl_name,
                output=tmp1,
                method="count",
                env=host_env,
            )
            maxvalue = gs.raster_info(tmp1)["max"]
            gs.mapcalc(
                f"{name} = if((isnull({tmp1}) || {maxvalue} == 0), 0, "
                f"({tmp1}/{maxvalue}) * {efficacy})",
                env=host_env,
            )
        params = {
                "treatments": name,
                "treatment_date": dateToString(dateFromString(self.params.model['treatment_date']).replace(year=year)),
                "treatment_length": self.model_settings.model["treatment_length"],
                "treatment_application": self.model_settings.model[
                    "treatment_application"
                ],
            }
        self.treatments_for_model.append(params)

    # def create_treatment_name(self, event, player, attempt, checkpoint):
    #     self.tr_merged_name = "__".join(
    #         [
    #             self.tr_tl_name,
    #             event,
    #             player,
    #             f"{attempt[0]}",
    #             str(max(0, checkpoint)),
    #         ]
    #     )
    #     return self.tr_merged_name

    def archive_treatments(self, event, player, attempt, checkpoint, use_dashboard):
        name = "__".join(
            [
                self.tr_tl_name,
                event,
                player,
                f"{attempt[0]}",
                str(max(0, checkpoint)),
            ]
        )
        if use_dashboard:
            gs.run_command("g.copy", vector=[self.tr_dashboard, name], overwrite=True, quiet=True)
        else:
            gs.run_command("g.copy", vector=[self.tr_tl_name, name], overwrite=True, quiet=True)
        return name

    def merge_treatment(self):
        tr_env = get_environment(raster=self.tr_registered_name)
        gs.run_command(
            "v.to.rast",
            input=self.tr_external_name,
            output=self.tr_external_name,
            type="area",
            use="val",
            env=tr_env,
        )
        gs.run_command(
            "r.patch",
            input=[self.tr_registered_name, self.tr_external_name],
            output=self.tr_merged_name,
            env=tr_env,
        )

    def resample(self, env):
        treatments = self.tr_merged_name
        efficacy = self.model_settings.pops["efficacy"]
        host = self.model_settings.model["host"]
        tmp1 = "tmp_resampled"
        tmp2 = "tmp_proportion"
        if not self.do_resampling:
            gs.mapcalc(
                "{tr_new} = if(isnull({tr}), 0, float({tr}) * {eff})".format(
                    tr_new=tmp1, tr=treatments, eff=efficacy
                ),
                env=env,
            )
            gs.run_command("g.rename", raster=[tmp1, treatments], env=env)
            return

        if gs.raster_info(treatments)["ewres"] < gs.raster_info(host)["ewres"]:
            gs.run_command(
                "r.resamp.stats",
                input=treatments,
                output=tmp1,
                flags="w",
                method="count",
                env=env,
            )
            maxvalue = gs.raster_info(tmp1)["max"]
            gs.mapcalc(
                "{p} = if((isnull({t}) || {m} ==0), 0, ({t}/{m}) * {eff})".format(
                    p=tmp2,
                    t=tmp1,
                    m=maxvalue,
                    eff=efficacy,
                ),
                env=env,
            )
        else:
            gs.run_command(
                "r.resamp.stats",
                input=treatments,
                output=tmp1,
                flags="w",
                method="average",
                env=env,
            )
            gs.mapcalc(
                "{p} = if(isnull({t}), 0, {t} * {eff})".format(
                    p=tmp2, t=tmp1, eff=efficacy
                ),
                env=env,
            )
        gs.run_command("g.rename", raster=[tmp2, treatments], env=env)

    def compute_registered_treatment_area(self, use_dashboard):
        if use_dashboard:
            vector = self.tr_dashboard
        else:
            vector = self.tr_tl_name
        data = gs.read_command(
            "v.to.db",
            map=vector,
            option="area",
            flags="pc",
            units="meters",
            separator="comma"
        )
        area = float(data.strip().splitlines()[-1].split(",")[-1])
        return area

    # def compute_treatment_area(self, env):
    #     # compute separately area of external polygons and TL polygons
    #     data = gs.read_command(
    #         "v.to.db",
    #         map=self.tr_external_name,
    #         option="area",
    #         flags="pc",
    #         units="meters",
    #         separator="comma",
    #         env=env,
    #     )
    #     area_external = float(data.strip().splitlines()[-1].split(",")[-1])
    #     host = self.model_settings.model["host"]
    #     tmp = "tmp_exclude_host"
    #     gs.mapcalc(
    #         "{n} = if (isnull({t}) || {host} == 0, null(), {t}) ".format(
    #             host=host, t=self.tr_registered_name, n=tmp
    #         ),
    #         env=env,
    #     )
    #     univar = gs.parse_command(
    #         "r.univar", flags="g", map=self.tr_registered_name, env=env
    #     )
    #     gs.run_command("g.remove", type="raster", name=tmp, flags="f", env=env)
    #     if not univar or float(univar["sum"]) == 0:
    #         return 0 + area_external
    #     else:
    #         res = gs.region(env=env)
    #         return float(univar["n"]) * res["nsres"] * res["ewres"] + area_external

    def current_treatment_to_geojson(self, year):
        # convert to vector and compute feature area
        print("current treatm to geojson")
        print(self.tr_external_json)
        if gs.vector_info(self.tr_tl_name)["areas"] == 0:
            if self.tr_external_json:
                return json.dumps(self.tr_external_json)
            else:
                return None

        # create tmp location and reproject
        dbase = tempfile.mkdtemp()
        location = "tmp_pseudo_mercator"
        name = "treatment"
        gs.create_location(dbase=dbase, location=location, epsg=4326)
        gisrc, env = gs.create_environment(dbase, location, "PERMANENT")
        env["GRASS_VERBOSE"] = "0"
        env["GRASS_MESSAGE_FORMAT"] = "standard"
        genv = gs.gisenv()
        gs.run_command(
            "v.proj",
            dbase=genv["GISDBASE"],
            location=genv["LOCATION_NAME"],
            quiet=True,
            mapset=genv["MAPSET"],
            input=self.tr_tl_name,
            output=name,
            env=env,
        )
        # export json
        out_json = os.path.join(dbase, "tmp.json")
        gs.run_command(
            "v.out.ogr",
            input=name,
            flags="s",
            output=out_json,
            format_="GeoJSON",
            lco="COORDINATE_PRECISION=7",
            quiet=True,
            env=env,
        )
        # edit resulting json to add properties required by dashboard
        with open(out_json) as f:
            j = json.load(f)
        j.pop("name", None)
        j.pop("crs", None)
        efficacy = self.model_settings.pops["efficacy"]
        cost = self.model_settings.pops["cost_per_meter_squared"]
        date = dateToString(
            dateFromString(self.model_settings.model["treatment_date"]).replace(
                year=year
            )
        )
        fill_dict = {
            "management_type": "Host removal",
            "efficacy": float(efficacy),
            "cost": cost,
            "duration": 0,
            "date": date,
            "pesticide_type": None,
            "tangible": True,
        }
        for feat in j["features"]:
            feat["properties"].pop("value", None)
            feat["properties"].pop("label", None)
            feat["properties"]["id"] = uuid.uuid4().hex
            for prop in fill_dict:
                feat["properties"][prop] = fill_dict[prop]
        # merge with external polygons
        if self.tr_external_json:
            features = self.tr_external_json["features"]
            j["features"].extend(features)
        # cleanup
        gs.try_remove(gisrc)
        shutil.rmtree(dbase)

        return json.dumps(j)

    def current_geojson_to_treatment(
        self, management_polygons, year, run_collection=None
    ):
        """Convert json coming from dashboard for visualization on TL"""

        def reset_layers():
            self.treatments_for_model = []
            gs.run_command(
                "v.edit", map=self.tr_external_name, tool="create", env=self._env
            )
            gs.run_command(
                "v.edit",
                map=self.tr_dashboard,
                tool="create",
                env=self._env,
            )

        print(f"convert geojson {year}")
        # print(self.ignore_incoming)
        # if self.ignore_incoming:
        #     self.ignore_incoming = False
        #     return
        if not management_polygons or management_polygons == "0":
            self.tr_external_json = None
            self.tr_dashboard_json = None
            reset_layers()
            return
        j = json.loads(management_polygons)
        print(management_polygons)
        # filter to discard tangible polygons from this year
        # for merging with TL polygons to send to dashboard
        features = []
        for feat in j["features"]:
            y = dateFromString(feat["properties"]["date"]).year
            if "tangible" in feat["properties"]:
                continue
            if y != year:
                continue
            features.append(feat)
        j["features"] = features
        self.tr_external_json = j
        # filter to keep only external polygons for visualization
        j = json.loads(management_polygons)
        features = []
        for feat in j["features"]:
            if "tangible" not in feat["properties"]:
                # get only treatments from current year:
                d = feat["properties"]["date"]
                if dateFromString(d).year == year:
                    features.append(feat)
        j["features"] = features
        print("incoming json after filtering")
        print(j)
        if not features:
            reset_layers()
            return

        # create tmp location and reproject
        dbase = tempfile.mkdtemp()
        location = "tmp_pseudo_mercator"
        gs.create_location(dbase=dbase, location=location, epsg=4326)
        gisrc, env = gs.create_environment(dbase, location, "PERMANENT")
        env["GRASS_VERBOSE"] = "0"
        env["GRASS_MESSAGE_FORMAT"] = "standard"
        out_json = os.path.join(dbase, "tmp.json")
        # export for visualization
        with open(out_json, "w") as f:
            json.dump(j, f)
        gs.run_command(
            "v.in.ogr",
            input=out_json,
            flags="t",
            output=self.tr_external_name,
            quiet=True,
            env=env,
        )
        gs.run_command(
            "v.proj",
            dbase=dbase,
            location=location,
            mapset="PERMANENT",
            input=self.tr_external_name,
            output=self.tr_external_name,
            overwrite=True,
            quiet=True,
        )
        print('v.proj tmp_dashboard')
        # create input for model
        j = json.loads(management_polygons)
        self.tr_dashboard_json = j
        for feat in j["features"]:
            feat["properties"]["efficacy"] = float(feat["properties"]["efficacy"])
        with open(out_json, "w") as f:
            json.dump(j, f)
        gs.run_command(
            "v.in.ogr",
            input=out_json,
            output=self.tr_dashboard,
            quiet=True,
            env=env,
        )
        gs.run_command(
            "v.proj",
            dbase=dbase,
            location=location,
            mapset="PERMANENT",
            input=self.tr_dashboard,
            output=self.tr_dashboard,
            overwrite=True,
            quiet=True,
        )
        # create rasters for spread model
        self.create_treatment_rasters_from_dashboard()
        # cleanup
        gs.try_remove(gisrc)
        shutil.rmtree(dbase)

    def create_treatment_rasters_from_dashboard(self):
        host = self.model_settings.model["host"]
        host_env = get_environment(raster=host)
        res = gs.region(env=host_env)["ewres"]
        high_res_env = get_environment(raster=host, res=res / 5)
        need_resample = bool(
            "cell_treatment_proportion" in self.model_settings.pops
            and self.model_settings.pops["cell_treatment_proportion"]
        )
        env = host_env
        if need_resample:
            env = high_res_env
        tmp1 = "tmp_resampled"
        tmp2 = "tmp_proportion"
        distinct = gs.read_command(
            "v.db.select",
            map=self.tr_dashboard,
            col="distinct duration,date",
            flags="c",
        )
        combinations = []
        self.treatments_for_model = []
        for each in distinct.splitlines():
            duration, date = each.split("|")
            combinations.append((int(duration), date))
        for i, each in enumerate(combinations):
            name = f"{self.tr_registered_basename}__{i}"
            gs.run_command(
                "v.to.rast",
                input=self.tr_dashboard,
                type="area",
                where=f"duration = '{each[0]}' AND date = '{each[1]}'",
                use="attr",
                attribute_column="efficacy",
                output=name,
                env=env,
            )
            # recompute to get proportion efficacy
            if not need_resample:
                gs.run_command("r.null", map=name, null=0, env=env)
            else:
                gs.run_command(
                    "r.resamp.stats",
                    input=name,
                    output=tmp1,
                    method="average",
                    env=host_env,
                )
                gs.run_command(
                    "r.resamp.stats",
                    input=name,
                    output=tmp2,
                    method="count",
                    env=host_env,
                )
                maxvalue = gs.raster_info(tmp2)["max"]
                gs.mapcalc(
                    f"{name} = if((isnull({tmp1}) || {maxvalue} == 0), 0, "
                    f"({tmp2}/{maxvalue}) * {tmp1})",
                    env=host_env,
                )
            params = {
                "treatments": name,
                "treatment_date": each[1],
                "treatment_length": each[0],
                "treatment_application": self.model_settings.model[
                    "treatment_application"
                ],
            }
            self.treatments_for_model.append(params)

    def create_treatment_visualization_vector(self, env):
        """TODO: fix, base on vectors"""
        treatment = self.tr_merged_name
        tr, evt, plr, attempt, year = treatment.split("__")
        postfix = "cat_year"
        gs.mapcalc(
            "{n} = if({t} == 1, {y}, null())".format(
                n=treatment + "__" + postfix,
                t=treatment,
                y=int(year)
                + dateFromString(self.model_settings.model["start_date"]).year,
            ),
            env=env,
        )
        pattern = "__".join([tr, evt, plr, attempt, "*", postfix])
        mapset = gs.gisenv()["MAPSET"]
        layers = gs.list_grouped(type="raster", pattern=pattern)[mapset]
        to_patch = []

        for layer in layers:
            y = int(layer.split("__")[-2])
            if y <= int(year):
                to_patch.append(layer)
        name = "__".join([tr, evt, plr, attempt])
        if len(to_patch) >= 2:
            to_patch = gs.natural_sort(to_patch)[::-1]
            gs.run_command("r.patch", input=to_patch, output=name, flags="z", env=env)
        else:
            gs.run_command("g.copy", raster=[treatment + "__" + postfix, name], env=env)
        gs.run_command(
            "r.to.vect", input=name, output=name, flags="vt", type="area", env=env
        )

        if (
            "color_treatments" in self.model_settings.pops
            and self.model_settings.pops["color_treatments"]
        ):
            color = self.model_settings.pops["color_treatments"].split(".")
            if len(color) == 1:  # grass color table
                param = {"color": color[0]}
            else:  # user-defined color rules in file
                param = {
                    "rules": os.path.join(
                        self.workdir, self.model_settings.pops["color_treatments"]
                    )
                }
            gs.run_command("v.colors", map=name, use="cat", env=env, **param)
        return name
