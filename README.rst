Tangible Landscape
==================

Dependencies:
-------------
* GRASS GIS 7, latest trunk is needed (starting with `r67232 <https://trac.osgeo.org/grass/changeset/67232>`_ )
* Python package `watchdog <https://pypi.python.org/pypi/watchdog>`_, install for example using pip

Installation:
-------------

1. Install GRASS GIS 7.
#. Install GRASS GIS addon r.in.kinect
#. Install Python package watchdog using pip
#. Install Tangible Landscape plugin using g.extension:

    g.extension g.gui.tangible url=github.com/ncsu-osgeorel/grass-tangible-landscape

#. Open GRASS GIS and type this into GUI command console. A dialog should now open.

    g.gui.tangible
  



