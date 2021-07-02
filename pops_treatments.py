import os
import grass.script as gs
from tangible_utils import get_environment
from pops_dashboard import dateFromString


class Treatments:
    def __init__(self, study_area, workdir):
        self.model_settings = None
        self.tr_tl_name = None
        self.study_area = study_area
        self.workdir = workdir
        self.tr_registered_name = "tmp_registered_treatment"
        self._tr_registered = False
        self.do_resampling = True
        # default env
        self._env = get_environment(raster=self.study_area)

    def set_model_settings(self, model_settings):
        self.model_settings = model_settings
        self.tr_tl_name = model_settings.pops["treatments"]

    def register_treatment(self):
        """Register treatment from TL"""
        if not self._tr_registered:
            gs.run_command(
                "g.copy",
                raster=[self.tr_tl_name, self.tr_registered_name],
                env=self._env,
            )
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
        # TODO: send to dashboard

    def reset_registered_treatment(self):
        self._tr_registered = False

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
        host = self.model_settings.pops["host"]
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
        host = self.model_settings.pops["host"]
        tmp = treatments + "_exclude_host"
        gs.mapcalc(
            "{n} = if (isnull({t}) || {host} == 0, null(), {t}) ".format(
                host=host, t=treatments, n=tmp
            ),
            env=env,
        )
        univar = gs.parse_command("r.univar", flags="g", map=treatments, env=env)
        gs.run_command("g.rename", raster=tmp, env=env)
        if not univar or float(univar["sum"]) == 0:
            return 0
        else:
            res = gs.region(env=env)
            return float(univar["n"]) * res["nsres"] * res["ewres"]

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

    # def integrate_treatments_from_dashboard(self, json):
    #     pass
