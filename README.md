Tangible Landscape - Termites
==================
This README describes the installation of new version of Tangible Landscape which runs on Linux (Ubuntu) and Mac (OS X Yosemite). This repository contains also older, unsupported, version running solely on MS Windows.

Branch Termites_application is used for a serious game with termites spread using
[R model] (https://github.com/f-tonini/Termite-Dispersal-Simulation) by f. Tonini

Dependencies:
-------------

-   GRASS GIS 7, latest trunk is needed (starting with
    [r67232](https://trac.osgeo.org/grass/changeset/67232))
-   Python package [watchdog](https://pypi.python.org/pypi/watchdog),
    install for example using pip
-   GRASS GIS addon
    [r.in.kinect](https://github.com/ncsu-osgeorel/r.in.kinect)
-   [R model] (https://github.com/f-tonini/Termite-Dispersal-Simulation) (path to it needs to fixed in termites_gui.py)

Installation:
-------------

1.  Install GRASS GIS 7.
2.  Install GRASS GIS addon
    [r.in.kinect](https://github.com/ncsu-osgeorel/r.in.kinect)
3.  Install Python package watchdog using pip
4.  Open GRASS GIS and install Tangible Landscape plugin using g.extension:

        g.extension g.gui.tangible url=github.com/ncsu-osgeorel/grass-tangible-landscape/archive/termites_application.zip

6. Close and restart GUI with `g.gui`.
5.  Type this into GRASS GUI command console. A dialog
    should now open.

        g.gui.tangible
    
![Tangible Landscape plugin](https://github.com/ncsu-osgeorel/grass-tangible-landscape/blob/master/tangible_landscape_dialog.png "Tangible Landscape plugin")


