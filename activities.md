## Documentation of JSON configuration file for designing activities

Specification of directory where to find Python files with activity worflow for all activities. This is required.

    "taskDir": "/path/to/my/activities/",
   
Specification of directory where to write log files after each activity ends (useful for running experiments). This postprocessing is done inside the Python files describing the activity workflow in Python function starting with 'post_...'. This is optional.
   
    "logDir": "/path/to/logs/",
  
  
Specifies whether HTML (specifically reveal.js) slides should be used during the activity (useful for running experiments).
This has 2 items, one specifies directory where html slides are to be found, and the second determines the position where the window with slides will be opened. This is optional.

    "slides":
      {
         "dir": "/home/tangible/Rogers_experiment/experiment_slides2/",
         "position": [2000, 300]
      },
    
Specifies whether to show a sign after completeing each activity to indicate that users need to remove hands so that the scanner can capture final result (useful for experiments). Color, font size, position and text can be specified. This is optional.

    "handsoff": [
                 "d.text", 
                 "at=6,45",
                 "size=20",
                 "color=red",
                 "text='HANDS OFF'"
         ],
        
Specifies how much time the sign stays displayed to ensure completing each activity. Color, font size, position and text can be specified. This is optional, if not specified it's 0 s.
  
    "duration_handsoff": 6000,
    "duration_handsoff_after": 5000,
  
Key bindings for specific actions. In wxPython wx.WXK_F5 is 344 and so on.
  
    "keyboard_events": {"stopTask": 344, "scanOnce": 370},
  
This describes the activities:

    "tasks": [
      {
       "layers": [
        [
          "d.rast", 
          "map=freeplay_scan"
        ],
        [
          "d.vect", 
          "map=freeplay_contours"
        ],
      ],
       "layers_opacity": [1.0, 0.5],
       "calibration": false,
       "base": "cutfill1_dem1",
       "time_limit": 300, 
       "scanning_params": {"smooth": 10, "numscans": 2, "zexag": 1},
       "analyses": "experiment_freeplay.py", 
       "filter" : {"threshold": 200, "debug": true},
       "slides": {"switch": [93, 174], "file": "freeplay.html"},
       "profile": {"size": [400, 140], "position": [4272, 660],
                   "limitx": [0, 350], "limity": [90, 190], "ticks": 10, "raster": "freeplay_scan"},
       "title": "Task 0: Freeplay"
     },
    ]
   
Specification of GIS layers which should be loaded when the activity starts. The display will zoom to capture all these layers. The layer list can be empty if needed.

      "layers": [
        [
          "d.rast", 
          "map=freeplay_scan"
        ],
        [
          "d.vect", 
          "map=freeplay_contours"
        ],
      ],
 
This specifies the semitransparency of the layers (1 is opaque). The length of the list should be the same as the number of loaded layers.

    "layers_opacity": [1.0, 0.5], 

Sometimes it's necessary to capture the topography shape before the start of the activity, for example for detection of markers. Specifying 'true' will result in creating a 'calibrate' button for the activity. This is optional.
 
    "calibration": false,

Specifies a raster map used for georeferencing.

    "base": "cutfill1_dem1",

Specifies time limit for each activity (useful for experiments). This is optional.

    "time_limit": 300,
  
Specifies scanning parameters. This is optional, however the settings stay for next tasks unless other settings is specified there:

      "scanning_params": {"smooth": 10, "numscans": 2, "zexag": 1},

File with Python workflow for the activity (and postprocessing if desired). The directory is specified in 'taskDir' above.

      "analyses": "experiment_freeplay.py", 

Specifies filtering of scans to avoid scans with captured hands based on the range of elevation values of each scan. Debug=true outputs the elevation range in normal case without hands and alows in this way to pick the right threshold.

      "filter" : {"threshold": 200, "debug": true},

Allows to have activities which use continuous scanning (false) or just single scan (optional):

    "single_scan": true


Specifies details of the slides for each activity (when to switch slides and which html file to use). 'Switch' is a list of numbers telling the application when to switch to next slide, in this case next slide is switched after 93s and 174 s (from the beginning of the activity). 


    "slides": {"switch": [93, 174], "file": "freeplay.html"},

Specifies whether profile widget should be displayed, what is its size, position, limit on axes, and raster used for computing the profile:


    "profile": {"size": [400, 140], "position": [4272, 660],
               "limitx": [0, 350], "limity": [90, 190], "ticks": 10, "raster": "freeplay_scan"},
              
Specifies title of the activity:

      "title": "Task 0: Freeplay"

