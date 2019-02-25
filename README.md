Tangible Landscape
==================
This README describes the installation of Tangible Landscape which runs on Linux (tested with Ubuntu) and MacOS. The software is not tested on MS Windows (contributions are welcome). This repository contains also older, unsupported, version running solely on MS Windows.

Dependencies:
-------------

-   GRASS GIS 7.2
-   Python package [watchdog](https://pypi.python.org/pypi/watchdog), optionally [matplotlib](https://matplotlib.org/),
    install for example using pip
-   GRASS GIS addon
    [r.in.kinect](https://github.com/ncsu-osgeorel/r.in.kinect)

Installation using install script:
----------------------------------
This option is available only for Ubuntu 16.04 (tested for 17.04 as well), for other distributions please modify the script accordingly.


1. Make a folder where all the dependencies will be compiled:

    mkdir tangiblelandscape && cd tangiblelandscape
    
2. Download [install.sh](https://raw.githubusercontent.com/tangible-landscape/grass-tangible-landscape/master/install.sh) to that folder and run it:

       sh install.sh
    
    It will ask you for administrator password. You need to be online to download all dependencies. After finishing the process, log out and log in.
    
3. Find GRASS GIS in Dash and start it. Create a new GRASS Location or use an existing one, and when GRASS Layer Manager opens, go to tab Console and type:

       g.gui.tangible

Manual installation:
-------------

1.  Install GRASS GIS 7.2. You need to compile it yourself, because 7.2 is not released yet. For GRASS GIS compilation, see instructions for [r.in.kinect](https://github.com/ncsu-osgeorel/r.in.kinect).
2.  Install GRASS GIS addon
    [r.in.kinect](https://github.com/ncsu-osgeorel/r.in.kinect)
3.  Install Python package watchdog using pip

        sudo apt-get install python-pip
        sudo pip install watchdog
    
4.  Open GRASS GIS and install Tangible Landscape plugin using g.extension:

        g.extension g.gui.tangible url=github.com/tangible-landscape/grass-tangible-landscape

6. Close and restart GUI with `g.gui`.
5.  Type this into GRASS GUI command console. A dialog
    should now open.

        g.gui.tangible
    
![Tangible Landscape plugin](https://github.com/tangible-landscape/grass-tangible-landscape/wiki/img/plugin/scanning_tab.png "Tangible Landscape plugin")

Authors
--------
Anna Petrasova (lead developer), Vaclav Petras, Payam Tabrizian, Brendan Harmon, Helena Mitasova

NCSU GeoForAll Laboratory
