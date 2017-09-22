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
                playerIds.append(int(each['playerId']))
        return playerIds, playerNames

    def get_current_player(self):
        res = requests.get(self.root + '/current')
        if res.status_code == 404:
            return None, None
        data = res.json()
        return int(data[0]['playerId']), data[0]['playerName']

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
                            data={"locationId": self.locationId, "eventId": eventId, 'playerId': int(playerId)})
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
        if not baseline:
            baseline = [0, 0, 0, 0, 0, 0]
        self._filePath = filePath
        self.attempts = [str(i) for i in range(1, 50)]
        self._template = \
        """{{
            "attempt": {attempt},
            "baseline": {baseline},
            "data": [
                {{"axis": "Number of Dead Tanoaks", "value": {sndo} }},
                {{"axis": "Percentage of Dead Tanoaks", "value": {spdo} }},
                {{"axis": "Infected Area (ha)", "value": {sia} }},
                {{"axis": "Money Spent", "value": {sms} }},
                {{"axis": "Area Treated", "value": {sat} }},
                {{"axis": "Price per Saved Tanoak", "value": {sppo} }}
            ],
            "tableRows": [
                {{"column": "Number of Dead Tanoaks", "value": \"{ndo}\" }},
                {{"column": "Percentage of Dead Tanoaks", "value": {pdo} }},
                {{"column": "Infected Area (ha)", "value": {ia} }},
                {{"column": "Money Spent", "value": \"{ms}\" }},
                {{"column": "Area Treated (ha)", "value": {at} }},
                {{"column": "Price per Saved Tanoak", "value": {ppo} }}
            ]
        }}"""
        scaled = {'sndo': 10, 'spdo': 10, 'sia': 10, 'sms': 0, 'sat': 0, 'sppo': 0}
        table = {'ndo': str(baseline[0])[:-3] + 'K', 'pdo': '{:2.1f}'.format(100 * baseline[1]), 'ia': baseline[2],
                 'ms': baseline[3], 'at': '{:2.1f}'.format(baseline[4]/ 10000.),
                 'ppo': '{:2.1f}'.format(baseline[5])}

        scaled.update(table)
        baseline = self._template.format(attempt='null', baseline='true', **scaled)
        self._data = [json.loads(baseline)]
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

        scaled = {'sndo': radarValues[0], 'spdo': radarValues[1], 'sia': radarValues[2],
                  'sms': radarValues[3], 'sat': radarValues[4], 'sppo': radarValues[5]}
        table = {'ndo': str(tableValues[0])[:-3] + 'K', 'pdo': '{:2.1f}'.format(100 * tableValues[1]), 'ia': tableValues[2],
                 'ms': str(int(tableValues[3]))[:-3] + 'K', 'at': '{:2.1f}'.format(tableValues[4] / 10000.),
                 'ppo': '{:2.1f}'.format(tableValues[5])}
        scaled.update(table)
        data = self._template.format(attempt='"{a}"'.format(a=self.attempts[att_indx]),
                                     baseline='false', **scaled)
        print data
        self._data.append(json.loads(data))
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
            baseline = [0, 0, 0, 0, 0, 0]
        self._filePath = filePath
        self._data = \
        [
            {
                "axis": "Number of Dead Tanoaks",
                "options": False,
                "values": [
                    {"value": baseline[0], "playerName": "Baseline", "attempt": ""}
                ]
            },
            {
                "axis": "Percentage of Dead Tanoaks",
                "options": False,
                "values": [
                    {"value": baseline[1], "playerName": "Baseline", "attempt": ""}
                ]
            },
            {
                "axis": "Infected Area (ha)",
                "options": False,
                "values": [
                    {"value": baseline[2], "playerName": "Baseline", "attempt": ""}
                ]
            },
            {
                "axis": "Money Spent",
                "options": {"money": True},
                "values": [
                    {"value": baseline[3], "playerName": "Baseline", "attempt": ""}
                ]
            },
            {
                "axis": "Area Treated (ha)",
                "options": False,
                "values": [
                    {"value": baseline[4], "playerName": "Baseline", "attempt": ""}
                ]
            },
            {
                "axis": "Price per Saved Tanoak",
                "options": {"negative": True},
                "values": [
                    {"value": baseline[5], "playerName": "Baseline", "attempt": ""}
                ]
            }
        ]
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
            self._addRecord(i, value, player)

    def addRecordNDeadOaks(self, value, player):
        self._addRecord(self, 0, value, player)

    def addPercDeadOaks(self, value, player):
        self._addRecord(self, 1, value, player)

    def addInfectedArea(self, value, player):
        self._addRecord(self, 2, value, player)

    def addMoneySpent(self, value, player):
        self._addRecord(self, 3, value, player)

    def addAreaTreated(self, value, player):
        self._addRecord(self, 4, value, player)

    def addPricePerOak(self, value, player):
        self._addRecord(self, 5, value, player)

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
    dashboard = DashBoardRequests()
    eventIds = dashboard.get_events()
    eid = eventIds.keys()[0]
    playerIds, playerNames = dashboard.get_players(eid)
    fp = '/tmp/SOD_{evt}.json'.format(evt=eventIds[eid])
    #fp_baseline = '/tmp/SOD_{evt}_baseline.json'.format(evt=eventIds[eid])

    baseline = (56784, 5.898, 3417, 0, 0, 0)
    #barBaseline = BarData(filePath=fp_baseline, baseline=baseline)
    bar = BarData(filePath=fp, baseline=baseline)

    #dashboard.post_baseline_bar(fp_baseline)
    try:
        barjson = dashboard.get_data_barJson(eid)
        bar.setDataFromJson(barjson)
    except requests.exceptions.HTTPError:
        pass

    bar.addRecord((15000, 6, 1500, 500, 200, 10), playerNames[2])
    dashboard.post_data_bar(fp, eid)


    bar.addRecord((20000, 8, 1000, 1000, 100, 10), playerNames[0])
    dashboard.post_data_bar(fp, eid)

    bar.addRecord((10000, 8, 2000, 1000, 100, 10), playerNames[0])
    dashboard.post_data_bar(fp, eid)

    bar.addRecord((500, 2, 3000, 100, 10, 100), playerNames[1])
    dashboard.post_data_bar(fp, eid)

#    fp = '/tmp/SOD_{evt}_baseline.json'.format(evt=eventIds[eid])
#    baseline = (10000, 5.898, 3417, 0, 0, 0)
#    radar = RadarData(filePath=fp, baseline=baseline)
#    dashboard.post_baseline_radar(fp)

    for each in playerIds:
        fp = '/tmp/SOD_{evt}_{pl}.json'.format(evt=eventIds[eid], pl=each)
        radar = RadarData(filePath=fp, baseline=baseline)
        try:
            radarjson = dashboard.get_data_radarJson(eid, each)
            radar.setDataFromJson(radarjson)
        except requests.exceptions.HTTPError:
            pass

        radarValues = {'sndo': 5, 'spdo': 5, 'sia': 5, 'sms': 3, 'sat': 3, 'sppo': 3}
        tableValues = {'ndo': baseline[0], 'pdo': baseline[1], 'ia': baseline[2],
                       'ms': baseline[3], 'at': baseline[4], 'ppo': baseline[5]}
        radar.addRecord(radarValues, tableValues, baseline=False)
        dashboard.post_data_radar(fp, eventId=eid, playerId=each)

    radarValues = {'sndo': 10, 'spdo': 3, 'sia': 5, 'sms': 2, 'sat': 3, 'sppo': 1}
    radar.addRecord(radarValues, tableValues, baseline=False)
    dashboard.post_data_radar(fp, eventId=eid, playerId=1)

    radarValues = {'sndo': 1, 'spdo': 3, 'sia': 10, 'sms': 2, 'sat': 3, 'sppo': 1}
    radar.addRecord(radarValues, tableValues, baseline=False)
    dashboard.post_data_radar(fp, eventId=eid, playerId=1)

    radarValues = {'sndo': 9, 'spdo': 3, 'sia': 10, 'sms': 7, 'sat': 3, 'sppo': 6}
    radar.addRecord(radarValues, tableValues, baseline=False)
    dashboard.post_data_radar(fp, eventId=eid, playerId=1)
    radar.removeLast()
    dashboard.post_data_radar(fp, eventId=eid, playerId=1)
    #bar.removeLast()
        #dashboard.post_data_bar(fp, eid)

if __name__ == '__main__':
    main()