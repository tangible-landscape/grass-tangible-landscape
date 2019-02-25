# Documentation of JSON config file for designing activities

## General settings
The following settings do not depend on the activities.

### Path to workflow files
Specification of directory where to find Python files with activity worflow for all activities. By default, it is the directory where this configuration file is.

```json
   "taskDir": "/path/to/my/activities/",
```

### Logging and postprocessing
Specification of directory where to write log files after each activity ends (useful for running experiments).
This postprocessing is done inside the Python files describing the activity workflow in Python function
starting with `post_...`. This is optional.

```json
  "logDir": "/path/to/logs/",
```

### Slides
Specifies whether HTML (specifically [reveal.js](http://lab.hakim.se/reveal-js/)) slides
should be used during the activity (useful for running experiments).
This has 2 items, one specifies directory where html slides are to be found,
and the second determines the position where the window with slides will be opened. This is optional.

```json
  "slides":
    {
        "dir": "/home/tangible/Rogers_experiment/experiment_slides2/",
        "position": [2000, 300]
    },
```

### Show sign to remove hands
Specifies whether to show a sign after completeing each activity to indicate
that users need to remove hands so that the scanner can capture final result (useful for experiments).
Color, font size, position and text can be specified. This is optional.

```json
  "handsoff": [
                "d.text", 
                "at=6,45",
                "size=20",
                "color=red",
                "text='HANDS OFF'"
        ],
 ```
 
Specifies how much time the sign stays displayed to ensure completing each activity.
Color, font size, position and text can be specified. This is optional, if not specified it's 0 s.

```json
  "duration_handsoff": 6000,
  "duration_handsoff_after": 5000,
```

### Key bindings
Key bindings for specific actions. In wxPython, for example, `wx.WXK_F5` is 344 and so on.
You can find a list of key event names [here](https://wxpython.org/Phoenix/docs/html/wx.KeyCode.enumeration.html#wx-keycode).
Available actions are `stopTask` (user can stop activity this way, for example using a button),
`scanOnce` (used in cases when we don't need to run analysis continuously during
the activity, but need to capture and analyze the scan just when the user needs it),
`taskNext`
This is optional, you can use any of them.

| Action | Description |
| --- | ----------- |
| scanOnce | Used in cases when we don't need to run analysis continuously during the activity, but need to capture and analyze the scan just when the user needs it |
| startTask | Start currently selected task|
| taskNext | Switch to next task (stop currently running one) |
| taskPrevious | Switch to previous task (stop currently running one)|
| stopTask | User can stop activity this way, for example using a button, or a slide advancer with extra button |
| mycustomTask | User can define custom task, the task is then defined in the Python file of the activity in a function with name starting with 'mycustomTask' (whatever you specified in the config file) |


```json
    "keyboard_events": {"stopTask": 344, "scanOnce": 370},
```

## Activity description
This describes the activities (explained further below):

```json
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
    }
   ]
```

### Title and instructions
Specifies title of the activity:

```json
 "title": "Task 0: Freeplay"
```

Specifies the instructions for the activity:

```json
 "instructions": "Place marker to create viewshed"
```


### Layers

Specification of GIS layers which should be loaded when the activity starts.
The specification of the symbology is given using
[d.rast](https://grass.osgeo.org/grass74/manuals/d.rast.html) and
[d.vect](https://grass.osgeo.org/grass74/manuals/d.vect.html) GRASS GIS modules.
Note that the specified layers must exist when the activity starts,
otherwise the loading will fail.
This is __required__, however the layer list can be empty if needed.
Special d.* commands (d.legend, d.northarrow, d.barscale, d.rgb, d.shade, d.labels) are supported as well.

```json
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
```

This specifies the semitransparency of the layers (1 is opaque).
The length of the list should be the same as the number of loaded layers. Optional.

```json
 "layers_opacity": [1.0, 0.5], 
```

This specifies the whether the layers should be checked (by default they are all checked).
The length of the list should be the same as the number of loaded layers. Optional.

```json
 "layers_checked": [true, false], 
```

Specifies a raster map used for georeferencing, _required_.

```json
 "base": "cutfill1_dem1",
```

### Processing

File with Python workflow for the activity (and postprocessing if desired).
The directory is specified in 'taskDir' above. This is _required_.

```json
 "analyses": "experiment_freeplay.py", 
```


Sometimes it's necessary to capture the topography shape before the start of the activity,
for example for detection of markers. Specifying 'true' will result in creating a 'calibrate' button for the activity. When calibrating a raster called 'scan_saved' is created. See also 'calibration_scanning_params'.
This is optional.

```json
 "calibration": false,
```


Item 'scanning_params' specifies scanning parameters. This is optional, however the settings stay for next
tasks unless other settings is specified there. Item 'calibration_scanning_params' set scanning parameter specifically for calibration phase: first 'scanning_params' are set and then 'calibration_scanning_params' are set (so in this example we end up with `{"smooth": 10, "numscans": 2, "zexag": 1, "interpolate": true}` for calibration).

```json
 "scanning_params": {"smooth": 10, "numscans": 2, "zexag": 1, "interpolate": false},
 "calibration_scanning_params": {"interpolate": true},
```

Allows to have activities which use continuous scanning (false) or just single scan (optional):

```json
"single_scan": true,
```

Specifies filtering of scans to avoid scans with captured hands based on the range of elevation values of each scan.
Debug=true outputs the elevation range in normal case without hands and allows in this way to pick the right threshold.

```json
 "filter" : {"threshold": 200, "debug": true},
```

### Additional widgets


Specifies whether profile widget should be displayed,
what is its size, position, limit on axes, and raster used for computing the profile:

```json
"profile": {"size": [400, 140], "position": [4272, 660],
            "limitx": [0, 350], "limity": [90, 190], "ticks": 10, "raster": "freeplay_scan"},
 ```

This is how the profile gets updated from a Python workflow file:

 ```python
 from activities import updateProfile

def run_freeplay(scanned_elev, eventHandler, env, **kwargs):
     event = updateProfile(points=[(640026, 223986), (640334, 223986)])
     eventHandler.postEvent(receiver=eventHandler.activities_panel, event=event)
 ```


Specifies whether dashboard widget should be displayed:
```json
"display": {"multiple": true, "average": 2, "size": [600, 180], "position": [2800, 900],
            "fontsize": 12, "maximum": [100, 20, 6, 60, 2.5, 8],
            "formatting_string": ["{:.0f} %", "{:g}", "{:g}","{:.1f}","{:.2f}","{:.1f}"],
            "title": ["Remediated", "Patch #", "Richness", "Mean size", "Shannon", "Shape ind." ]}
    },
```

In both cases (profile and widget), size and position can be specified in absolute or relative coordinates. 

|  | Size |Position | Description|
| --- | ----------- | --- | --- |
| Absolute | "size" | "position" | (x, y)/(width, height) screen coordinates |
| Relative | "relative_size" | "relative_position" | coordinates relative to map display from 0-1 , origin is TL corner|


### Misc

Specifies time limit for each activity (useful for experiments). This is optional.

```json
 "time_limit": 300,
```



Specifies details of the slides for each activity (when to switch slides and which html file to use).
'Switch' is a list of numbers telling the application when to switch to next slide,
in this case next slide is switched after 93s and 174 s (from the beginning of the activity). 

```json
"slides": {"switch": [93, 174], "file": "freeplay.html"},
```




