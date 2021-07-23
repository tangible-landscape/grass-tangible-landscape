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
        self._tr_registered = False
        self.tr_external_name = "external_treatment"
        self.tr_external_json = None
        self.do_resampling = True
        self._env = None

    def initialize(self, model_settings, study_area, workdir):
        self.model_settings = model_settings
        self.tr_tl_name = model_settings.pops["treatments"]
        self.workdir = workdir
        self.study_area = study_area
        # default env
        self._env = get_environment(raster=self.study_area)
        gs.run_command(
            "v.edit", map=self.tr_external_name, tool="create", env=self._env
        )

    def register_treatment(self):
        """Register treatment from TL"""
        if not self._tr_registered:
            gs.run_command(
                "g.copy",
                raster=[self.tr_tl_name, self.tr_registered_name],
                env=self._env,
            )
            self._tr_registered = True
            return

        registered_info = gs.raster_info(self.tr_registered_name)
        new_info = gs.raster_info(self.tr_tl_name)
        if registered_info["nsres"] > new_info["nsres"]:
            align = self.tr_tl_name
        else:
            align = self.tr_registered_name

        if "region" in self.model_settings.pops:
            env = get_environment(
                region=self.model_settings.pops["region"], align=align
            )
        else:
            env = get_environment(raster=self.study_area, align=align)

        gs.run_command(
            "r.patch",
            input=[self.tr_registered_name, self.tr_tl_name],
            output=self.tr_registered_name,
            env=env,
        )
        self._tr_registered = True
        # TODO: send to dashboard

    def reset_registered_treatment(self):
        self._tr_registered = False

    def is_treatment_registered(self):
        return self._tr_registered

    def name_treatment(self, event, player, attempt, checkpoint):
        tr_name = "__".join(
            [
                self.tr_tl_name,
                event,
                player,
                f"{attempt[0]}",
                str(max(0, checkpoint)),
            ]
        )
        gs.run_command(
            "g.copy", raster=[self.tr_registered_name, tr_name], env=self._env
        )
        return tr_name

    def resample(self, treatments, env):
        efficacy = self.model_settings.pops["efficacy"]
        host = self.model_settings.model["host"]
        tmp1 = treatments + "_resampled"
        tmp2 = treatments + "_proportion"
        if not self.do_resampling:
            gs.mapcalc(
                "{tr_new} = if(isnull({tr}), 0, float({tr}) * {eff} / 100)".format(
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
                "{p} = if((isnull({t}) || {m} == 0), 0, ({t} / {m}) * ({eff} / 100))".format(
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
                "{p} = if(isnull({t}), 0, {t} * ({eff} / 100))".format(
                    p=tmp2, t=tmp1, eff=efficacy
                ),
                env=env,
            )
        gs.run_command("g.rename", raster=[tmp2, treatments], env=env)

    def compute_treatment_area(self, treatments, env):
        host = self.model_settings.model["host"]
        tmp = treatments + "_exclude_host"
        gs.mapcalc(
            "{n} = if (isnull({t}) || {host} == 0, null(), {t}) ".format(
                host=host, t=treatments, n=tmp
            ),
            env=env,
        )
        univar = gs.parse_command("r.univar", flags="g", map=treatments, env=env)
        gs.run_command("g.remove", type="raster", name=tmp, flags="f", env=env)
        if not univar or float(univar["sum"]) == 0:
            return 0
        else:
            res = gs.region(env=env)
            return float(univar["n"]) * res["nsres"] * res["ewres"]

    def current_treatment_to_geojson(self, year):
        # convert to vector and compute feature area
        tr_env = get_environment(raster=self.tr_tl_name)
        gs.run_command(
            "r.to.vect",
            input=self.tr_tl_name,
            output=self.tr_tl_name,
            type="area",
            # flags="s",
            env=tr_env,
        )
        gs.run_command(
            "v.to.db",
            map=self.tr_tl_name,
            option="area",
            columns="area",
            units="meters",
            env=tr_env,
        )
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
            "efficacy": float(efficacy) / 100,
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
        j = json.loads(management_polygons)
        # filter to discard tangible polygons from this year
        features = []
        for feat in j["features"]:
            y = dateFromString(feat["properties"]["date"]).year
            if "tangible" in feat["properties"] and y == year:
                continue
            features.append(feat)
        j["features"] = features
        self.tr_external_json = j
        # filter to keep only external polygons
        j = json.loads(management_polygons)
        features = []
        for feat in j["features"]:
            if "tangible" not in feat["properties"]:
                # get only treatments from current year:
                d = feat["properties"]["date"]
                if dateFromString(d).year == year:
                    features.append(feat)
        j["features"] = features
        if not features:
            gs.run_command(
                "v.edit", map=self.tr_external_name, tool="create", env=self._env
            )
            return

        # create tmp location and reproject
        dbase = tempfile.mkdtemp()
        location = "tmp_pseudo_mercator"
        gs.create_location(dbase=dbase, location=location, epsg=4326)
        gisrc, env = gs.create_environment(dbase, location, "PERMANENT")
        env["GRASS_VERBOSE"] = "0"
        env["GRASS_MESSAGE_FORMAT"] = "standard"
        out_json = os.path.join(dbase, "tmp.json")
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
        # cleanup
        gs.try_remove(gisrc)
        shutil.rmtree(dbase)

    def create_treatment_vector(self, treatment, env):
        # assumes full name of treatment
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
