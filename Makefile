MODULE_TOPDIR = ../..

PGM= g.gui.tangible

ETCFILES = tangible_utils change_handler analyses current_analyses drawing export color_interaction activities activities_profile activities_dashboard activities_slides TSP blender

include $(MODULE_TOPDIR)/include/Make/Script.make
include $(MODULE_TOPDIR)/include/Make/Python.make

default: script
