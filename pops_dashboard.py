# -*- coding: utf-8 -*-
"""
Created on Wed Aug 23 09:29:18 2017

@author: anna
"""

import json
import requests


class DashBoardRequests:
    def __init__(self):
        self.locationId = 1
        self.root = None
        self.bardataId = None
        self.barBaselineId = None
        self.radardataIds = {}
        self.radarBaselineId = None

    def set_root_URL(self, url):
        self.root = url

    def get_events(self):
        """[{"_id":1000,"name":"MyNewEvent","locationId":"1","__v":0}]"""
        res = requests.get(self.root + '/event/location/{lid}'.format(lid=self.locationId))
        res.raise_for_status()
        eventNames = []
        eventIds = []
        for each in res.json():
            eventIds.append(int(each['_id']))
            for char in ".-+ &%#@!?,():'":
                each['name'] = each['name'].replace(char, '_')
            eventNames.append(each['name'])
        return eventIds, eventNames

    def get_current_event(self):
        """Should be run only when we have selected player"""
        res = requests.get(self.root + '/current')
        if res.status_code == 404:
            return None
        data = res.json()
        return int(data[0]['eventId'])

    def get_players(self, eventId):
        res = requests.get(self.root + '/player/{eid}'.format(eid=eventId))
        res.raise_for_status()
        playerNames = []
        playerIds = []
        for each in res.json():
                playerNames.append(each['playerName'])
                playerIds.append(each['playerId'])
        return playerIds, playerNames

    def get_current_player(self):
        res = requests.get(self.root + '/current')
        if res.status_code == 404:
            return None, None
        data = res.json()
        return data[0]['playerId'], data[0]['playerName']

    def get_data_barJson(self, eventId):
        try:
            res = requests.get(self.root + '/charts/bar/', params={'locationId': self.locationId, 'eventId': eventId})
            res.raise_for_status()
            return res.json()
        except requests.exceptions.HTTPError:
            return None

    def get_data_barId(self, eventId):
        res = requests.get(self.root + '/charts/barId', params={"locationId": self.locationId, "eventId": eventId})
        res.raise_for_status()
        self.bardataId = res.json()[0]['_id']
        return self.bardataId

    def get_data_radarJson(self, eventId, playerId):
        try:
            res = requests.get(self.root + '/charts/radar', params={"locationId": self.locationId, "eventId": eventId, "playerId": playerId})
            res.raise_for_status()
            return res.json()
        except requests.exceptions.HTTPError:
            return None

    def get_data_radarId(self, eventId, playerId):
        res = requests.get(self.root + '/charts/radarId', params={"locationId": self.locationId,
                                                                  "eventId": eventId, "playerId": playerId})
        res.raise_for_status()
        self.radardataIds[playerId] = res.json()[0]['_id']
        return self.radardataIds[playerId]

    # data bar
    def post_data_bar(self, jsonfile, eventId):
        if self.bardataId:
            self._delete_data_bar(self.bardataId)
        else:
            try:
                self.bardataId = self.get_data_barId(eventId)
                self._delete_data_bar(self.bardataId)
            except requests.exceptions.HTTPError:
                pass

        self.bardataId = self._post_data_bar(jsonfile, eventId)

    def _post_data_bar(self, jsonfile, eventId):
        post_data = {'file': open(jsonfile, 'rb')}
        res = requests.post(self.root + '/charts/bar', files=post_data, data={"locationId": self.locationId, "eventId": eventId})
        res.raise_for_status()
        return res.json()['id']

    def _delete_data_bar(self, fid):
        res = requests.delete(self.root + '/charts/bar/{bid}'.format(bid=self.bardataId))
        res.raise_for_status()

    # baseline bar
    def get_baseline_barJson(self):
        try:
            res = requests.get(self.root + '/charts/barBaseline', params={"locationId": self.locationId})
            res.raise_for_status()
            return res.json()
        except requests.exceptions.HTTPError:
            return None

    def get_baseline_barId(self):
        res = requests.get(self.root + '/charts/barBaselineId', params={"locationId": self.locationId})
        res.raise_for_status()
        self.barBaselineId = res.json()['_id']
        return res.json()

    def post_baseline_bar(self, jsonfile):
        try:
            self._delete_baseline_bar()
        except requests.exceptions.HTTPError:
            pass
        self._post_baseline_bar(jsonfile)

    def _post_baseline_bar(self, jsonfile):
        post_data = {'file': open(jsonfile, 'rb')}
        res = requests.post(self.root + '/charts/barBaseline', files=post_data, data={"locationId": self.locationId})
        res.raise_for_status()

    def _delete_baseline_bar(self):
        res = requests.delete(self.root + '/charts/barBaseline/', params={'locationId': self.locationId})
        res.raise_for_status()

    # radar data
    def post_data_radar(self, jsonfile, eventId, playerId):
        if playerId in self.radardataIds:
            self._delete_data_radar(self.radardataIds[playerId])
        else:
            try:
                self.radardataIds[playerId] = self.get_data_radarId(eventId, playerId)
                self._delete_data_radar(self.radardataIds[playerId])
            except requests.exceptions.HTTPError:
                pass

        self.radardataIds[playerId] = self._post_data_radar(jsonfile, eventId, playerId)

    def _post_data_radar(self, jsonfile, eventId, playerId):
        post_data = {'file': open(jsonfile, 'rb')}
        res = requests.post(self.root + '/charts/radar', files=post_data,
                            data={"locationId": self.locationId, "eventId": eventId, 'playerId': playerId})
        res.raise_for_status()
        return res.json()['id']

    def _delete_data_radar(self, fid):
        res = requests.delete(self.root + '/charts/radar/{bid}'.format(bid=fid))
        res.raise_for_status()

    # radar baseline
    def get_baseline_radarJson(self):
        try:
            res = requests.get(self.root + '/charts/radarBaseline', params={"locationId": self.locationId})
            res.raise_for_status()
            return res.json()
        except requests.exceptions.HTTPError:
            return None

    def post_baseline_radar(self, jsonfile):
        try:
            self._delete_baseline_radar()
        except requests.exceptions.HTTPError:
            pass

        self._post_baseline_radar(jsonfile)

    def _post_baseline_radar(self, jsonfile):
        post_data = {'file': open(jsonfile, 'rb')}
        res = requests.post(self.root + '/charts/radarBaseline', files=post_data, data={"locationId": self.locationId})
        res.raise_for_status()

    def get_baseline_radarId(self):
        res = requests.get(self.root + '/charts/radarBaselineId', params={"locationId": self.locationId})
        res.raise_for_status()
        self.radarBaselineId = res.json()['_id']
        return res.json()

    def _delete_baseline_radar(self):
        res = requests.delete(self.root + '/charts/radarBaseline/', params={'locationId': self.locationId})
        res.raise_for_status()


class RadarData:
    def __init__(self, filePath, baseline=None):
        self.columns = ["Infected Area (mi2)", "Money Spent", "Area Treated (mi2)", "Crop affected (mi2)"]
        self.formatting = ["{:.1f}", "{:.0f} M", "{:.1f}", "{:.1f}"]
        self.multiplication = [3.861e-7, 1/1000000., 3.861e-7, 3.861e-7]
        if not baseline:
            baseline = [0, 0, 0, 0]
        scaled = [10, 0, 0, 0]
        self._filePath = filePath
        self.attempts = [str(i) for i in range(1, 50)]
        self._data = [{'data': [], 'tableRows':[], 'attempt': None, "baseline": True}]
        i = 0
        for c, f, m in zip(self.columns, self.formatting, self.multiplication):
            self._data[0]['data'].append({'axis': c, 'value': scaled[i]})
            self._data[0]['tableRows'].append({'column': c, 'value': f.format(baseline[i] * m)})
            i += 1
        self.save()

    def setDataFromJson(self, jsonString):
        self._data = jsonString
        self.save()

    def getBaselineValues(self):
        radar = []
        for each in self._data[0]['tableRows']:
            radar.append(each['value'])
        return radar

    def getBaselineScaledValues(self):
        radar = []
        for each in self._data[0]['data']:
            radar.append(each['value'])
        return radar

    def save(self):
        with open(self._filePath, 'w') as f:
            f.write(json.dumps(self._data, indent=4))

    def addRecord(self, radarValues, tableValues, baseline=False):
        att_indx = -1
        for each in self._data:
            if each['attempt'] is None:
                continue
            tmp = self.attempts.index(each['attempt'])
            if tmp > att_indx:
                att_indx = tmp
        att_indx += 1

        self._data.append({'data': [], 'tableRows': [], 'attempt': str(self.attempts[att_indx]), "baseline": False})
        i = 0
        for c, f, m in zip(self.columns, self.formatting, self.multiplication):
            self._data[-1]['data'].append({'axis': c, 'value': radarValues[i]})
            self._data[-1]['tableRows'].append({'column': c, 'value': f.format(tableValues[i] * m)})
            i += 1

        self.save()

    def removeAttempt(self, attempt):
        i = -1
        found = False
        for each in self._data:
            i += 1
            if each['attempt'] == self.attempts[attempt - 1]:
                found = True
                break
        if found:
            del self._data[i]
            self.save()


class BarData:
    def __init__(self, filePath, baseline=None):
        if not baseline:
            baseline = [0, 0, 0, 0]
        columns = ["Infected Area (mi2)", "Money Spent (M)", "Area Treated (mi2)", "Crop affected (mi2)"]
        self.formatting = [lambda x: round(x, 1), int, lambda x: round(x, 1), lambda x: round(x, 1)]
        self.multiplication = [3.861e-7, 1/1000000., 3.861e-7, 3.861e-7]
        self._filePath = filePath
        self._data = []
        i = 0
        for each in columns:
            col = {"axis": each, "options": False, "values": [{"value": self.formatting[i](baseline[i] * self.multiplication[i]), "playerName": "No treatment", "attempt": ""}]}
            self._data.append(col)
            i += 1
        self.save()

    def save(self):
        with open(self._filePath, 'w') as f:
            f.write(json.dumps(self._data, indent=4))

    def setDataFromJson(self, jsonString):
        self._data = jsonString
        self.save()

    def getBaseline(self):
        baseline = []
        for each in self._data:
            baseline.append(each['values'][0]['value'])
        return baseline

    def addRecord(self, values, player):
        for i, value in enumerate(values):
            self._addRecord(i, self.formatting[i](value * self.multiplication[i]), player)

    def _addRecord(self, which, value, player):
        cnt_attempt = 1
        for each in self._data[which]['values']:
            if player == each['playerName']:
                cnt_attempt += 1
        dictionary = {"value": value, "playerName": player, "attempt": cnt_attempt}
        self._data[which]['values'].append(dictionary)
        self.save()

    def getAllAttempts(self, playerName):
        attempts = []
        for each in self._data[0]['values']:
            if playerName == each['playerName']:
                attempts.append(int(each['attempt']))
        return attempts

    def removeAttempt(self, playerName, attempt):
        for each in self._data:
            for i, item in enumerate(each['values']):
                if item['playerName'] == playerName and item['attempt'] == attempt:
                    del each['values'][i]
                    break
        self.save()


def main():
    # BEFORE RUNNING:
    # create an event, create at least one player and set him as playing
    dashboard = DashBoardRequests()
    dashboard.set_root_URL('http://localhost:3000')
    eids, enames = dashboard.get_events()
    events = dict(zip(eids, enames))
    eid = dashboard.get_current_event()
    import os, tempfile, shutil
    tmpdir = tempfile.mkdtemp()

    playerIds, playerNames = dashboard.get_players(eid)
    fp = os.path.join(tmpdir, 'SOD_{evt}.json'.format(evt=events[eid]))
    fp_baseline = os.path.join(tmpdir, 'SOD_{evt}_baseline.json'.format(evt=events[eid]))

    baseline = (3417, 0, 0)
    barBaseline = BarData(filePath=fp_baseline, baseline=baseline)
    bar = BarData(filePath=fp, baseline=baseline)

    dashboard.post_baseline_bar(fp_baseline)
    dashboard.post_data_bar(fp_baseline, eid)
    try:
        barjson = dashboard.get_data_barJson(eid)
        bar.setDataFromJson(barjson)
    except requests.exceptions.HTTPError:
        pass

    bar.addRecord((1500, 500, 200), playerNames[0])
    dashboard.post_data_bar(fp, eid)

    bar.addRecord((1000, 100, 10), playerNames[0])
    dashboard.post_data_bar(fp, eid)

    bar.addRecord((2000, 1000, 100), playerNames[0])
    dashboard.post_data_bar(fp, eid)

    bar.addRecord((3000, 100, 10), playerNames[0])
    dashboard.post_data_bar(fp, eid)

    fp = os.path.join(tmpdir, 'SOD_{evt}_baseline.json'.format(evt=events[eid]))
    baseline = (3417, 0, 0)
    radar = RadarData(filePath=fp, baseline=baseline)
    dashboard.post_baseline_radar(fp)

    for each in playerIds:
        fp = os.path.join(tmpdir, 'SOD_{evt}_{pl}.json'.format(evt=events[eid], pl=each))
        radar = RadarData(filePath=fp, baseline=baseline)
        try:
            #radarjson = dashboard.get_data_radarJson(eid, each)
            #radar.setDataFromJson(radarjson)
            pass
        except requests.exceptions.HTTPError:
            pass
        dashboard.post_data_radar(fp, eventId=eid, playerId=each)

        radarValues = [1, 2, 3]
        tableValues = [baseline[0], baseline[1], baseline[2]]
        radar.addRecord(radarValues, tableValues, baseline=False)
        dashboard.post_data_radar(fp, eventId=eid, playerId=each)

    shutil.rmtree(tmpdir)


if __name__ == '__main__':
    main()
