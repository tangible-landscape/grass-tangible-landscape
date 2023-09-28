# -*- coding: utf-8 -*-
"""
@brief activities_profile

This program is free software under the GNU General Public License
(>=v2). Read the file COPYING that comes with GRASS for details.

@author: Anna Petrasova (akratoc@ncsu.edu)
"""

from numpy import interp, sqrt, arange
import matplotlib

matplotlib.use("WXAgg")

from matplotlib.backends.backend_wxagg import FigureCanvasWxAgg as FigureCanvas
from matplotlib.figure import Figure

import grass.script as gscript

import wx


class ProfileFrame(wx.Frame):
    def __init__(self, parent):
        wx.Frame.__init__(self, parent)
        self.figure = Figure(figsize=(0.1, 0.1))
        self.axes = self.figure.add_subplot(111)
        self.canvas = FigureCanvas(self, -1, self.figure)
        self.sizer = wx.BoxSizer(wx.VERTICAL)
        self.sizer.Add(self.canvas, 1, wx.LEFT | wx.TOP | wx.GROW)
        self.SetSizer(self.sizer)
        self.Fit()

        self.distances = []
        self.elevations = []
        self.point_distances = []
        self.point_elevations = []
        self.limx = [0, 1]
        self.limy = [0, 1]
        self.ticks = 1

    def set_xlim(self, lim):
        self.limx = lim

    def set_ylim(self, lim):
        self.limy = lim

    def set_ticks(self, ticks):
        self.ticks = ticks

    def distance(self, p1, p2):
        return sqrt(
            (p1[0] - p2[0]) * (p1[0] - p2[0]) + (p1[1] - p2[1]) * (p1[1] - p2[1])
        )

    def compute_profile(self, points, raster, env):
        if not points:
            self.draw(clear=True)
            return
        coords = []
        for p in points:
            coords.append("{},{}".format(p[0], p[1]))
        data = gscript.read_command(
            "r.profile", input=raster, coordinates=coords, quiet=True, env=env
        ).strip()
        self.distances = []
        self.elevations = []
        for line in data.splitlines():
            dist, elev = line.strip().split()
            self.distances.append(float(dist))
            self.elevations.append(float(elev))

        d_start = 0
        self.point_distances = [d_start]
        self.point_elevations = [interp(d_start, self.distances, self.elevations)]
        for i in range(1, len(points)):
            d = d_start + self.distance(points[i - 1], points[i])
            d_start = d
            e = interp(d, self.distances, self.elevations)
            self.point_distances.append(d)
            self.point_elevations.append(e)
        self.draw()

    def draw(self, clear=False):
        self.axes.clear()
        self.axes.set_ylim(self.limy)
        self.axes.set_xlim(self.limx)
        major_ticks = arange(self.limy[0], self.limy[1], self.ticks)
        self.axes.set_yticks(major_ticks)
        self.axes.yaxis.grid(True, alpha=0.7)
        if not clear:
            self.axes.annotate(
                "A",
                xy=(self.point_distances[0], self.point_elevations[0]),
                xycoords="data",
                xytext=(self.point_distances[0], self.point_elevations[0]),
                horizontalalignment="right",
                verticalalignment="top",
            )
            self.axes.annotate(
                "B",
                xy=(self.point_distances[-1], self.point_elevations[-1]),
                xycoords="data",
                xytext=(self.point_distances[-1], self.point_elevations[-1]),
                textcoords="data",
                horizontalalignment="left",
                verticalalignment="top",
            )
            self.axes.plot(self.distances, self.elevations, color="black")
            self.axes.plot(
                self.point_distances,
                self.point_elevations,
                marker="o",
                linestyle="None",
                color="red",
            )
        self.canvas.draw()


if __name__ == "__main__":
    app = wx.App()
    fr = ProfileFrame(None)
    fr.SetPosition((800, 100))
    fr.SetSize((900, 300))
    fr.compute_profile(
        points=[
            (301771.285097, 206878.390929),
            (302068.909287, 207180.593952),
            (302609.211663, 207311.090713),
        ],
        raster="DEM_asheville_flow@task_flow",
        env=None,
    )
    fr.draw()
    fr.Show()

    app.MainLoop()
