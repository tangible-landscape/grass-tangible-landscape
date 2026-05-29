Tangible Landscape
==================
![header image](readme_image.jpg "Tangible Landscape plugin")

Tangible Landscape is an open source tangible interface for geospatial modeling powered by GRASS. Tangible Landscape couples a physical model with a digital model of a landscape so that you can naturally feel, reshape, and interact with the landscape. This makes geographic information systems (GIS) far more intuitive and accessible for beginners, empowers geospatial experts, and creates new opportunities for developers.

This repository contains Tangible Landscape plugin for GRASS, which allows
a real-time feedback cycle of interaction, 3D scanning, point cloud processing, geospatial computation and projection

<p align="center">
<img src="https://github.com/tangible-landscape/tangible-landscape-media/blob/master/tl_logo/tl_logo.png?raw=true" alt="Tangible Landscape logo" width="150"/></p>

Installation:
----------------------------------
We support installation on Ubuntu 24.04. Tangible Landscape supports the Orbbec Femto Bolt, Microsoft Azure Kinect (K4A), and the Kinect for Xbox One. Software dependencies include:

-   GRASS >= 8.5 (cmake-based build)
-   GRASS addon [r.in.kinect](https://github.com/tangible-landscape/r.in.kinect): choose the branch matching your sensor (`femto-bolt`, `k4a`, or `xbox-one`).
-   Python package [watchdog](https://pypi.python.org/pypi/watchdog), optionally [matplotlib](https://matplotlib.org/)

1. Make a folder where all the dependencies will be compiled:

       mkdir tangiblelandscape && cd tangiblelandscape

2. Download [one of the install scripts](https://github.com/tangible-landscape/tangible-landscape-install) matching your Ubuntu version and sensor to that folder and run it, e.g.:

       sh install_Ubuntu-24.04_femto-bolt.sh

    It will ask you for administrator password. You need to be online to download all dependencies. After finishing the process, log out and log in.

    To install only the plugin (e.g. when r.in.kinect is already set up), use `g.extension`:

       git clone https://github.com/tangible-landscape/grass-tangible-landscape
       sudo grass --tmp-project XY --exec \
           g.extension -s extension=g.gui.tangible url=$(pwd)/grass-tangible-landscape

    The `-s` flag installs system-wide under `$GISBASE`; drop it (and `sudo`) for a per-user install.

3. Find GRASS in Dash and start it. Create a new GRASS project or use an existing one, and when GRASS Layer Manager opens, go to tab Console and type:

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
 - See [published research](https://tangible-landscape.github.io/publications.html)



Authors
--------
Anna Petrasova (lead developer), Vaclav Petras, Payam Tabrizian, Brendan Harmon, Helena Mitasova

[NCSU GeoForAll Laboratory](https://geospatial.ncsu.edu/geoforall/) at the [Center for Geospatial Analytics](https://cnr.ncsu.edu/geospatial/), NCSU

How to cite
-----------
If you are using Tangible Landscape in an academic context, please cite our work:

> Petrasova, A., Harmon, B., Petras, V., Tabrizian, P., & Mitasova, H. (2018). Tangible Modeling with Open Source GIS. Second edition. Springer International Publishing. eBook ISBN: 978-3-319-89303-7, Hardcover ISBN: 978-3-319-89302-0, https://doi.org/10.1007/978-3-319-89303-7.
