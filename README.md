Tangible Landscape
==================
![header image](readme_image.jpg "Tangible Landscape plugin")

Tangible Landscape is an open source tangible interface for geospatial modeling powered by GRASS GIS. Tangible Landscape couples a physical model with a digital model of a landscape so that you can naturally feel, reshape, and interact with the landscape. This makes geographic information systems (GIS) far more intuitive and accessible for beginners, empowers geospatial experts, and creates new opportunities for developers.

This repository contains Tangible Landscape plugin for GRASS GIS, which allows
a real-time feedback cycle of interaction, 3D scanning, point cloud processing, geospatial computation and projection

<p align="center">
<img src="https://github.com/tangible-landscape/tangible-landscape-media/blob/master/tl_logo/tl_logo.png?raw=true" alt="Tangible Landscape logo" width="150"/></p>

Installation:
----------------------------------
We support installation on Ubuntu 18.04, for other versions and Linux distributions please modify the script accordingly. Tangible Landscape requires Microsoft Kinect for Xbox (v2). Software dependencies include:

-   GRASS GIS >= 7.2
-   GRASS GIS addon [r.in.kinect](https://github.com/ncsu-osgeorel/r.in.kinect)
-   Python package [watchdog](https://pypi.python.org/pypi/watchdog), optionally [matplotlib](https://matplotlib.org/)

1. Make a folder where all the dependencies will be compiled:

       mkdir tangiblelandscape && cd tangiblelandscape

2. Download [install.sh](install.sh) to that folder and run it:

       sh install.sh

    It will ask you for administrator password. You need to be online to download all dependencies. After finishing the process, log out and log in.

3. Find GRASS GIS in Dash and start it. Create a new GRASS Location or use an existing one, and when GRASS Layer Manager opens, go to tab Console and type:

       g.gui.tangible


<p align="center">
<img src="tangible_landscape_dialog.png" alt="Tangible Landscape plugin" /></p>


Resources
--------
 - Visit [Tangible Landscape website](https://tangible-landscape.github.io) for overview and applications
 - Go to [Tangible Landscape wiki](https://github.com/tangible-landscape/grass-tangible-landscape/wiki)
 to see how to build and run Tangible Landscape and how to develop your applications for it
 - Check out [Community](https://github.com/tangible-landscape/grass-tangible-landscape/wiki/Community)
 page to see who is using Tangible Landscape
 - Read our book [Tangible Modeling with Open Source GIS](https://link.springer.com/book/10.1007%2F978-3-319-89303-7) showing various modeling applications and methods



Authors
--------
Anna Petrasova (lead developer), Vaclav Petras, Payam Tabrizian, Brendan Harmon, Helena Mitasova

[NCSU GeoForAll Laboratory](https://geospatial.ncsu.edu/geoforall/) at the [Center for Geospatial Analytics](https://cnr.ncsu.edu/geospatial/), NCSU
