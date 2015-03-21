Tangible Landscape
==============

Warning: this description is not complete

Installation:
-------------
Install GRASS GIS and Tangible Landscape:
 * Install GRASS GIS 7, not to Program Files, create your own directory for programs where you have write access
 * Make sure you can see hidden files and then go to someusername\\AppData\\Roaming\\GRASS7
 * if there is no GRASS7 directory, create it
 * in GRASS7 create directory guiplugins
 * download this repository as a zipfile
 * move grass_changed_files/frame.py to where GRASS is installed  (C:\\Users\\someuser\\MyPrograms\\GRASS GIS 7.0.0\\gui\\wxpython\\lmgr) and replace the file frame.py
 * copy the rest of the files and directory kinect (not kinect_source - this is not needed) to just created guiplugins directory

Run application
---------------
First do calibration:
 * launch the installed GRASS and you should see a dialog with multiple buttons
 * remove model from the table so that there is nothing on the table
 * click on button Calibrate and repeat if needed
 * if the angle is too big, manually adjust Kinect and repeat
 * when done, move back the model

Run scanning:
 * press Start and a Kinect app window appears
