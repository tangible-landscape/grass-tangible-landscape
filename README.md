Tangible Landscape
==================

Dependencies:
-------------

-   GRASS GIS 7, latest trunk is needed (starting with
    [r67232](https://trac.osgeo.org/grass/changeset/67232))
-   Python package [watchdog](https://pypi.python.org/pypi/watchdog),
    install for example using pip
-   GRASS GIS addon
    [r.in.kinect](https://github.com/ncsu-osgeorel/r.in.kinect)

Installation:
-------------

1.  Install GRASS GIS 7.
2.  Install GRASS GIS addon
    [r.in.kinect](https://github.com/ncsu-osgeorel/r.in.kinect)
3.  Install Python package watchdog using pip
4.  Open GRASS GIS and install Tangible Landscape plugin using g.extension:

    > g.extension g.gui.tangible
    > url=github.com/ncsu-osgeorel/grass-tangible-landscape

5.  Type this into GRASS GUI command console. A dialog
    should now open.

    > g.gui.tangible


