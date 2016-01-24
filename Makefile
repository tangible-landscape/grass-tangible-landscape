MODULE_TOPDIR = ../..

PGM= g.gui.tangible

ETCFILES = run_analyses utils change_handler analyses prepare_calibration current_analyses

include $(MODULE_TOPDIR)/include/Make/Script.make
include $(MODULE_TOPDIR)/include/Make/Python.make

default: script
