MODULE_TOPDIR = ../..

PGM= g.gui.tangible

ETCFILES = tangible_utils change_handler analyses current_analyses drawing export color_interaction experiment experiment_profile experiment_display experiment_slides TSP

include $(MODULE_TOPDIR)/include/Make/Script.make
include $(MODULE_TOPDIR)/include/Make/Python.make

default: script
