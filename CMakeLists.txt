cmake_minimum_required(VERSION 3.22)

project(g.gui.tangible LANGUAGES NONE)

include(build_addon)

add_files_to_etc_dir(${PROJECT_NAME}
  FILES
    tangible_utils.py
    change_handler.py
    analyses.py
    current_analyses.py
    drawing.py
    export.py
    activities.py
    activities_profile.py
    activities_dashboard.py
    activities_slides.py
    TSP.py
    blender.py)

build_addon(
  ${PROJECT_NAME}
  SOURCES ${PROJECT_NAME}.py
  DOCFILES
    ${PROJECT_NAME}.html
    ${PROJECT_NAME}.md)
