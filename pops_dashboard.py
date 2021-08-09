# -*- coding: utf-8 -*-
"""
Created on Wed Aug 23 09:29:18 2017

@author: anna
"""
import os
import shutil
import requests
import tempfile
import threading
import wx
import re
import math
import json
import datetime
import aiohttp
from urllib.parse import urlparse
from jsonrpc_websocket import Server as jsonrpc

import grass.script as gscript
from grass.exceptions import CalledModuleError

from tangible_utils import get_environment

threadDone, EVT_THREAD_DONE = wx.lib.newevent.NewEvent()


class ModelParameters:
    def __init__(self):
        self._web = None
        self._pops_config = None
        self._workdir = None
        self.model_name = None
        self.model = {}
        self.pops = {}
        self.baseline = {}
        self.model_flags = None
        self.baseline_flags = None

    def set_web_dashboard(self, dashboard):
        self._web = dashboard

    def set_config(self, config_dict, workdir):
        self._pops_config = config_dict
        self._workdir = workdir

    def read_initial_params(self):
        # start with config file and then replace by web dashboard
        self.pops = self._pops_config.copy()
        self.pops.pop("model")
        self.model = self._pops_config["model"].copy()
        self.model_name = self.model.pop("model_name")
        self.model_flags = self.model.pop("flags", None)
        # weather
        if "temperature_coefficient_file" in self._pops_config["model"]:
            self.model["temperature_coefficient_file"] = os.path.join(
                self._workdir,
                self._pops_config["model"]["temperature_coefficient_file"],
            )
        if "moisture_coefficient_file" in self._pops_config["model"]:
            self.model["moisture_coefficient_file"] = os.path.join(
                self._workdir, self._pops_config["model"]["moisture_coefficient_file"]
            )
        if "weather_coefficient_file" in self._pops_config["model"]:
            self.model["weather_coefficient_file"] = os.path.join(
                self._workdir, self._pops_config["model"]["weather_coefficient_file"]
            )
        if "temperature_file" in self._pops_config["model"]:
            self.model["temperature_file"] = os.path.join(
                self._workdir, self._pops_config["model"]["temperature_file"]
            )

        fh, path = tempfile.mkstemp()
        self.model["spread_rate_output"] = path
        os.close(fh)

        # assume dashboard is initialized
        if self._web:
            session = self._web.get_session()
            self.model["reproductive_rate"] = float(session["reproductive_rate"])
            # disable this for now
            # self.model['natural_distance'] = float(session['distance_scale'])
            self.pops["weather"] = session["weather"]

        self.baseline = self.model.copy()
        self.baseline.pop("single_series", None)
        self.baseline.pop("average_series", None)
        self.baseline.update(self._pops_config["baseline"])
        self.baseline_flags = self.baseline.pop("flags")
        self.pops.pop("baseline")

    def update(self):
        if self._web:
            run_collection = self._web.get_runcollection_params()
            print("update")
            print(run_collection)
            self.pops["budget"] = float(run_collection["budget"])
            self.pops["random_seed"] = float(run_collection["random_seed"])

    def UnInit(self):
        if "spread_rate_output" in self.model:
            gscript.try_remove(self.model["spread_rate_output"])


class PoPSDashboard(wx.EvtHandler):
    def __init__(self):
        wx.EvtHandler.__init__(self)
        self._root = None
        self._wsroot = None
        self._ws_auth_url = None
        self._runcollection = {}
        self._runcollection_id = None
        self._run = None
        self._run_id = None
        self._session = None
        self._session_id = None
        self._create_new = False
        self._temp_location = "temp_export_location_" + str(os.getpid())
        try:
            gscript.run_command(
                "g.proj", epsg=4326, location=self._temp_location, quiet=True
            )
        except CalledModuleError:
            # assume it's because it is already there
            pass

        gisrc, env = self._get_gisrc_environment()
        self._tmpgisrc = gisrc
        self._env = env
        self._tmp_out_file = gscript.tempfile(False)
        suffix = os.path.basename(gscript.tempfile(False)).replace(".", "_")
        self._tmp_vect_file = "tmp_vect_" + suffix
        self._tmp_inf_file = "tmp_inf_" + suffix
        self._tmp_infavg_file = "tmp_infavg_" + suffix
        self._last_name_suffix = None
        self._websocket_auth_headers = []
        self._ws_session = None
        self._ws_client = None
        self._username = None
        self._password = None
        self.Bind(EVT_THREAD_DONE, self._on_thread_done)

    def initialize(self, settings):
        url = settings["url"]
        sid = str(settings["session"])
        self._session_id = sid
        self._root = os.path.join("https://", url, "api", "")
        self._wsroot = os.path.join("wss://", url, "ws", "dashboard", sid, "")
        self._ws_auth_url = os.path.join("https://", url, "accounts", "login", "")
        self._username = settings["username"]
        self._password = settings["password"]

    def update_incoming_management_callback(self, callback):
        self._ws_client.update_management = callback

    async def connect(self, callback):
        """Connecting to webSocket server
        websockets.client.connect returns a WebSocketClientProtocol,
        which is used to send and receive messages
        """
        if not self._websocket_auth_headers:
            await self.authenticate()
        self._ws_session = aiohttp.ClientSession(headers=self._websocket_auth_headers)
        self._ws_client = jsonrpc(self._wsroot, session=self._ws_session)
        # If 'update_management' message received, send to update_message() function.
        self._ws_client.update_management = callback
        await self._ws_client.ws_connect()
        await self.get_external_management()

    async def authenticate(self):
        """
        Authenticate against the AUTH_URL using the provided USERNAME and PASSWORD

        :return: websocket auth headers
        """

        async with aiohttp.ClientSession(raise_for_status=True) as session:
            aiohttp.CookieJar(unsafe=True)
            # First GET the auth url to get a valid CSRF token
            resp = await session.get(self._ws_auth_url)
            csrf_token = resp.cookies.get("csrftoken").value

            # Then POST to it to get a new CSRF token and a session id
            session.cookie_jar.update_cookies(resp.cookies)
            resp = await session.post(
                self._ws_auth_url,
                allow_redirects=False,
                data={
                    "username": self._username,
                    "password": self._password,
                    "csrfmiddlewaretoken": csrf_token,
                },
            )
            csrf_token = resp.cookies.get("csrftoken").value
            session_id = resp.cookies.get("sessionid").value

            # Return the auth headers the websocket will need to connect
            parsed_auth_url = urlparse(self._ws_auth_url)
            websocket_auth_headers = [
                ("Origin", f"{parsed_auth_url.scheme}://{parsed_auth_url.netloc}"),
                ("Cookie", f"csrftoken={csrf_token}; sessionid={session_id}"),
            ]
            self._websocket_auth_headers = websocket_auth_headers

    async def send_management(self, json):
        if not json:
            return
        # we don't know when new rcoll is created
        # so we need to always ask for its id
        self.new_runcollection()
        await self._ws_client.update_management(
            management_polygons=json,
            run_collection=self._runcollection_id,
            _notification=True,
        )

    async def get_external_management(self):
        await self._ws_client.send_management_request(
            run_collection=self._runcollection_id, _notification=True
        )

    def set_management(self, geojson, cost, area, year):
        if geojson:
            j = json.loads(geojson)
            if j["features"]:
                self._run["management_polygons"] = j
                self._run["management_cost"] = "{v:.2f}".format(v=cost)
                self._run["management_area"] = "{v:.2f}".format(v=area)
            else:
                self._run["management_polygons"] = 0
                self._run["management_cost"] = 0
                self._run["management_area"] = 0
        else:
            self._run["management_polygons"] = 0
            self._run["management_cost"] = 0
            self._run["management_area"] = 0
        self._run["steering_year"] = year

    def _compare_runcollections(self, runc1, runc2):
        same = True
        for each in runc1.keys():
            if each in ("date_created", "status", "id"):
                continue
            try:
                if runc1[each] != runc2[each]:
                    same = False
                    break
            except KeyError:
                return False
        return same

    def _create_runcollection_name(self, name):
        namesp = name.split("_")
        if len(namesp) == 1:
            new = name + "_2"
        else:
            try:
                order = int(namesp[-1])
                order += 1
                namesp = namesp[:-1] + [str(order)]
                new = "_".join(namesp)
            except ValueError as e:
                new = name + "_2"
                print(e)
        return new

    def _get_runcollection(self, runcollection_id):
        try:
            res = requests.get(
                self._root + "run_collection_detail/" + runcollection_id + "/"
            )
            res.raise_for_status()
            return res.json()
        except requests.exceptions.HTTPError as e:
            print(e)
            return None

    def _get_runcollection_id(self):
        try:
            res = requests.get(self._root + "session_detail/" + self._session_id + "/")
            res.raise_for_status()
            runcollection_id = str(res.json()["most_recent_runcollection"])
            if runcollection_id == "null":
                return None
            return runcollection_id
        except requests.exceptions.HTTPError as e:
            print(e)
            return None

    def new_runcollection(self):
        self._runcollection_id = self._get_runcollection_id()
        # if something fails or there is no collection yet (when new session is created)
        if not self._runcollection_id:
            self._runcollection_id = self._create_runcollection(reuse=False)
            return
        print(self._runcollection_id)
        self._runcollection = self._get_runcollection(self._runcollection_id)
        print(self._runcollection)
        # this should never happen
        if not self._runcollection:
            self._runcollection_id = self._create_runcollection()
            return

        # if self._runcollection['second_most_recent_run'] != 'null':
        #     # needs to be created by TL
        #     self._runcollection_id = self._create_runcollection(reuse=True)

    def get_runcollection_params(self):
        return self._runcollection

    def session_name(self):
        if not self._session:
            return None
        return self._session["name"]

    def get_session_name(self):
        try:
            res = requests.get(self._root + "session_detail/" + self._session_id + "/")
            res.raise_for_status()
            self._session = res.json()
            return self._session["name"]
        except requests.exceptions.HTTPError as e:
            print(e)
            return None

    def get_session(self):
        try:
            res = requests.get(self._root + "session_detail/" + self._session_id + "/")
            res.raise_for_status()
            self._session = res.json()
            return res.json()
        except requests.exceptions.HTTPError as e:
            print(e)
            return {}

    def runcollection_name(self):
        if not self._runcollection:
            return None
        return self._runcollection["name"]

    def get_runcollection(self):
        if not self._runcollection_id:
            self.get_new_runcollection()
        try:
            res = requests.get(
                self._root + "run_collection_detail/" + self._runcollection_id + "/"
            )
            res.raise_for_status()
            name = res.json()["name"]
            return name
        except requests.exceptions.HTTPError as e:
            print(e)
            return None

    def get_runcollection_name(self):
        if not self._runcollection_id:
            self.get_new_runcollection()
        try:
            res = requests.get(
                self._root + "run_collection_detail/" + self._runcollection_id + "/"
            )
            res.raise_for_status()
            name = res.json()["name"]
            return name
        except requests.exceptions.HTTPError as e:
            print(e)
            return None

    def _create_runcollection(self, reuse=True):
        runcollection = self._runcollection.copy()
        runcollection["status"] = "PENDING"
        runcollection["date_created"] = None
        if reuse:
            runcollection["name"] = self._create_runcollection_name(
                runcollection["name"]
            )
            # change random seed so that the new collection looks different
            runcollection["random_seed"] = int(runcollection["random_seed"]) + 1
        else:
            runcollection["session"] = self._session_id
            runcollection["name"] = "First run"
            runcollection["random_seed"] = 1
            runcollection["budget"] = 1e6
            runcollection["cost_per_meter_squared"] = 1
        runcollection["status"] = "PENDING"

        try:
            res = requests.post(
                self._root + "run_collection_detail/", data=runcollection
            )
            res.raise_for_status()
            self._runcollection = res.json()
            self._runcollection_id = str(res.json()["id"])
            return self._runcollection_id
        except requests.exceptions.HTTPError as e:
            print(e)
            return None

    def create_run(self):
        self._run = {}
        self._run["status"] = "PENDING"
        self._run["run_collection"] = self._runcollection_id
        try:
            res = requests.post(self._root + "run_write/", data=self._run)
            res.raise_for_status()
            self._run = res.json()
            self._run_id = str(res.json()["id"])
            print("Created run id " + self._run_id)
            return self._run_id
        except requests.exceptions.HTTPError as e:
            print(e)
            return None

    def update_run(self):
        try:
            print(self._run)
            res = requests.put(
                self._root + "run_write/" + self._run_id + "/", json=self._run
            )
            res.raise_for_status()
            self._run = res.json()
            run_id = str(self._run["id"])
            print("Updated run id " + self._run_id)
            return run_id
        except requests.exceptions.HTTPError as e:
            print(res.json())
            print(e)
            return None

    def upload_results(
        self,
        year,
        probability,
        single_infected,
        average_infected,
        stddev_infected,
        min_infected,
        max_infected,
        spread_rate_file,
        rotation,
        use_single,
    ):
        env = get_environment(raster=probability)
        mapset = gscript.gisenv()["MAPSET"]
        gscript.mapcalc(
            "{n} = int(if({r} == 0, null(), {r}))".format(
                n=self._tmp_inf_file, r=single_infected
            ),
            env=env,
        )
        gscript.run_command(
            "g.copy",
            raster=[average_infected, self._tmp_infavg_file],
            overwrite=True,
            env=env,
        )
        gscript.run_command("r.null", map=self._tmp_infavg_file, setnull=0, env=env)

        results = process_for_dashboard(
            self._run_id,
            year,
            self._tmp_inf_file if use_single else self._tmp_infavg_file,
            spread_rate_file,
            rotation,
        )

        export_gisrc, export_env = self._create_tmp_gisrc_environment(
            self._temp_location
        )
        input_gisrc, input_env = self._create_tmp_gisrc_environment()
        t = threading.Thread(
            target=raster_to_proj_geojson_thread,
            args=(
                self,
                single_infected + "@" + mapset,
                probability + "@" + mapset,
                average_infected + "@" + mapset,
                stddev_infected + "@" + mapset,
                min_infected + "@" + mapset,
                max_infected + "@" + mapset,
                input_gisrc,
                input_env,
                export_gisrc,
                export_env,
                results,
                self._root,
                probability,
            ),
        )
        t.start()

    def run_done(self, last_name_suffix):
        self._last_name_suffix = last_name_suffix

    def _report_run_status(self, success=True):
        print("report_status_done for run " + self._run_id)
        self._run["status"] = "SUCCESS" if success else "FAILURE"
        try:
            res = requests.put(
                self._root + "run_write/" + self._run_id + "/", json=self._run
            )
            res.raise_for_status()
        except requests.exceptions.HTTPError as e:
            print(e)
            return None

    def report_runcollection_status(self, success=True):
        print("Report run collection done for " + self._runcollection_id)
        if not self._runcollection:
            return None
        self._runcollection["status"] = "SUCCESS" if success else "FAILURE"
        try:
            res = requests.put(
                self._root + "run_collection_write/" + self._runcollection_id + "/",
                data=self._runcollection,
            )
            res.raise_for_status()
            return res.json()["id"]
        except requests.exceptions.HTTPError as e:
            print(e)
            return None

    def _management_to_proj_geojson(self, vector, name, cat):
        genv = gscript.gisenv()
        gscript.run_command(
            "v.proj",
            location=genv["LOCATION_NAME"],
            quiet=True,
            mapset=genv["MAPSET"],
            input=vector,
            output=name,
            overwrite=True,
            env=self._env,
        )
        gscript.try_remove(self._tmp_out_file)
        gscript.run_command(
            "v.extract",
            input=name,
            cats=cat,
            output=name + "_extracted",
            env=self._env,
            quiet=True,
            overwrite=True,
        )
        gscript.run_command(
            "v.out.ogr",
            input=name + "_extracted",
            flags="sm",
            output=self._tmp_out_file,
            format_="GeoJSON",
            lco="COORDINATE_PRECISION=4",
            quiet=True,
            overwrite=True,
            env=self._env,
        )
        with open(self._tmp_out_file) as f:
            j = json.load(f)
        return j

    def _on_thread_done(self, event):
        if event.out_id is None:
            self._report_run_status(success=False)
            return
        res = re.search("[0-9]{4}_[0-9]{2}_[0-9]{2}", event.orig_name)
        if res and res.group() == self._last_name_suffix:
            self._report_run_status()
            self._last_name_suffix = None

    def _get_gisrc_environment(self):
        """Creates environment to be passed in run_command for example.
        Returns tuple with temporary file path and the environment. The user
        of this function is responsile for deleting the file."""
        env = os.environ.copy()
        genv = gscript.gisenv()
        tmp_gisrc_file = gscript.tempfile()
        with open(tmp_gisrc_file, "w") as f:
            f.write("MAPSET: {mapset}\n".format(mapset="PERMANENT"))
            f.write("GISDBASE: {g}\n".format(g=genv["GISDBASE"]))
            f.write("LOCATION_NAME: {l}\n".format(l=self._temp_location))
            f.write("GUI: text\n")
        env["GISRC"] = tmp_gisrc_file
        return tmp_gisrc_file, env

    def _create_tmp_gisrc_environment(self, location=None):
        """Creates environment to be passed in run_command for example.
        Returns tuple with temporary file path and the environment. The user
        of this function is responsile for deleting the file."""
        env = os.environ.copy()
        genv = gscript.gisenv()
        if not location:
            location = genv["LOCATION_NAME"]
        tmp_gisrc_file = gscript.tempfile()
        new_mapset = os.path.basename(
            os.path.normpath(
                tempfile.mkdtemp(dir=os.path.join(genv["GISDBASE"], location))
            )
        )
        with open(tmp_gisrc_file, "w") as f:
            f.write("MAPSET: {mapset}\n".format(mapset=new_mapset))
            f.write("GISDBASE: {g}\n".format(g=genv["GISDBASE"]))
            f.write("LOCATION_NAME: {l}\n".format(l=location))
            f.write("GUI: text\n")
        env["GISRC"] = tmp_gisrc_file
        env["GRASS_MESSAGE_FORMAT"] = "silent"
        env["GRASS_VERBOSE"] = "0"
        gscript.run_command("g.region", flags="do", env=env, quiet=True)
        gscript.run_command("db.connect", flags="c", env=env, quiet=True)
        return tmp_gisrc_file, env

    def close(self):
        path_to_location = os.path.join(
            gscript.gisenv()["GISDBASE"], self._temp_location
        )
        shutil.rmtree(path_to_location)
        os.remove(self._tmpgisrc)
        gscript.run_command(
            "g.remove", type="vector", name=self._tmp_vect_file, flags="f", quiet=True
        )
        gscript.run_command(
            "g.remove",
            type="raster",
            name=[self._tmp_inf_file, self._tmp_infavg_file],
            flags="f",
            quiet=True,
        )


def raster_to_proj_geojson_thread(
    evtHandler,
    single_raster,
    probability_raster,
    avg_raster,
    stddev_raster,
    min_raster,
    max_raster,
    input_gisrc,
    input_env,
    export_gisrc,
    export_env,
    results,
    root,
    probability,
):
    tempdir = tempfile.mkdtemp()
    tmp_layer1 = os.path.basename(tempdir) + "1"
    tmp_layer2 = os.path.basename(tempdir) + "2"
    tmp_file = os.path.join(tempdir, "out.json")

    input_env["GRASS_REGION"] = gscript.region_env(raster=single_raster)
    genv = gscript.gisenv(env=input_env)
    export_genv = gscript.gisenv(env=export_env)

    gscript.mapcalc(
        f"{tmp_layer1} = if({single_raster} > 0 ||| "
        f"{probability_raster} > 0 ||| "
        f"{avg_raster} > 0 ||| "
        f"{min_raster} > 0 ||| "
        f"{max_raster} > 0 ||| "
        f"{stddev_raster} > 0, "
        "row() + col(), null())",
        env=input_env,
    )
    # check for no outputs (eradication)
    if gscript.raster_info(tmp_layer1, env=input_env)["min"] is None:
        results["median_spread_map"] = {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "geometry": {"type": "Polygon", "coordinates": []},
                    "properties": {
                        "max": 0,
                        "min": 0,
                        "mean": 0,
                        "median": 0,
                        "probability": 0,
                        "standard_deviation": 0,
                    },
                }
            ],
        }
    else:
        gscript.run_command(
            "r.to.vect", input=tmp_layer1, output=tmp_layer1, type="area", env=input_env
        )
        columns = ["median", "probability", "mean", "min", "max", "standard_deviation"]
        rasters = [
            single_raster,
            probability_raster,
            avg_raster,
            min_raster,
            max_raster,
            stddev_raster,
        ]
        for col, r in zip(columns, rasters):
            gscript.run_command(
                "v.what.rast",
                map=tmp_layer1,
                type="centroid",
                raster=r,
                column=col,
                env=input_env,
            )
        gscript.run_command(
            "v.db.dropcolumn", map=tmp_layer1, column=["value", "label"], env=input_env
        )
        gscript.run_command(
            "v.proj",
            location=genv["LOCATION_NAME"],
            quiet=True,
            mapset=genv["MAPSET"],
            input=tmp_layer1,
            output=tmp_layer2,
            env=export_env,
        )
        gscript.run_command(
            "v.out.ogr",
            input=tmp_layer2,
            flags="sm",
            output=tmp_file,
            format_="GeoJSON",
            lco="COORDINATE_PRECISION=7",
            quiet=True,
            overwrite=True,
            env=export_env,
        )
        with open(tmp_file) as f:
            j = json.load(f)
            results["median_spread_map"] = j
        print(j)
    shutil.rmtree(tempdir)

    shutil.rmtree(
        os.path.join(
            export_genv["GISDBASE"], export_genv["LOCATION_NAME"], export_genv["MAPSET"]
        )
    )
    shutil.rmtree(os.path.join(genv["GISDBASE"], genv["LOCATION_NAME"], genv["MAPSET"]))
    os.remove(export_gisrc)
    os.remove(input_gisrc)
    try:
        with open("/tmp/test.txt", "w") as ff:
            ff.write(str(results))
        res = requests.post(root + "output/", json=results)
        res.raise_for_status()

        out_id = str(res.json()["pk"])
        print("Uploaded output with id " + out_id)
        evt = threadDone(out_id=out_id, orig_name=probability)
        wx.PostEvent(evtHandler, evt)
        return out_id
    except requests.exceptions.HTTPError as e:
        print(e)
        try:
            print(res.json())
        except:
            print("no json")
        evt = threadDone(out_id=None, orig_name=probability)
        wx.PostEvent(evtHandler, evt)
        return None


def process_for_dashboard(id_, year, raster, spread_rate_file, rotation=0):
    result = {"run": id_, "year": year}
    env = get_environment(raster=raster)
    data = gscript.parse_command("r.univar", map=raster, flags="gr", env=env)
    if not data or math.isnan(float(data["sum"])):
        data["n"] = data["sum"] = 0
    info = gscript.parse_command("r.info", flags="ge", map=raster, env=env)

    if info["title"].strip('"').startswith("Average"):
        text, area = info["description"].split(":")
        result["infected_area"] = "{v:.2f}".format(v=float(area.strip('"')))
    else:
        result["infected_area"] = "{v:.2f}".format(
            v=int(data["n"]) * float(info["nsres"]) * float(info["ewres"])
        )
    result["number_infected"] = int(float(data["sum"]))
    result["timetoboundary"] = {
        "north_time": 0,
        "south_time": 0,
        "east_time": 0,
        "west_time": 0,
    }
    result["distancetoboundary"] = {
        "north_distance": 0,
        "south_distance": 0,
        "east_distance": 0,
        "west_distance": 0,
    }
    # spread rate
    n = s = e = w = 0
    with open(spread_rate_file, "r") as f:
        lines = f.readlines()
        for line in lines:
            if line.startswith(str(year)):
                y, n, s, e, w = line.strip().split(",")
    ee, nn, ww, ss = 0, 90, 180, 270
    directions = {-90: s, 0: e, 90: n, 180: w, 270: s, 360: e}
    nr = directions[nn + rotation]
    sr = directions[ss + rotation]
    er = directions[ee + rotation]
    wr = directions[ww + rotation]
    result["spreadrate"] = {
        "north_rate": int(nr) if nr != "nan" else 0,
        "south_rate": int(sr) if sr != "nan" else 0,
        "east_rate": int(er) if er != "nan" else 0,
        "west_rate": int(wr) if wr != "nan" else 0,
    }

    return result


def dateFromString(date):
    return datetime.datetime.strptime(date, "%Y-%m-%d")


def dateToString(date):
    return date.strftime("%Y-%m-%d")
