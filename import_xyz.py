#-------------------------------------------------------------------------------
# Name:        module1
# Purpose:
#
# Author:      akratoc
#
# Created:     30/10/2013
# Copyright:   (c) akratoc 2013
# Licence:     <your licence>
#-------------------------------------------------------------------------------
import os
import sys
import atexit
import math
from tempfile import mkstemp

from grass.script import core as gcore
from grass.script import raster as grast

from scan_process import read_from_ascii, difference, adjust_scanned_elev, \
  adjust_boundaries, remove_fuzzy_edges, calibrate, smooth


def import_scan_rinxyz(input_file, real_elev, output_elev, output_diff, mm_resolution, calib_raster=None):
    output_tmp1 = "output_scan_tmp1"
    output_tmp2 = "output_scan_tmp2"
    output_tmp3 = "output_scan_tmp3"
    mm_resolution *= 1000

    fd, temp_path = mkstemp()
    os.close(fd)
    os.remove(temp_path)
    read_from_ascii(input_file=input_file, output_file=temp_path)
    gcore.use_temp_region()
    
    x_min, x_max, y_min, y_max = remove_fuzzy_edges(input_file=temp_path, output_file=temp_path, resolution=mm_resolution)

    gcore.run_command('g.region', n=y_max, s=y_min, e=x_max, w=x_min, res=mm_resolution)
    gcore.run_command('r.in.xyz', separator=" ", input=temp_path, output=output_tmp1, overwrite=True)

    info = grast.raster_info(output_tmp1)
    if  math.isnan(info['min']) or math.isnan(info['max']):
        gcore.run_command('g.remove', rast=output_tmp1)
        return

    


    gcore.run_command('r.region', map=output_tmp1, raster=real_elev, align=real_elev)
    gcore.run_command('g.region', rast=output_tmp1)

    if calib_raster:
        calibrate(scanned_elev=output_tmp1, calib_elev=calib_raster, new=output_tmp2)
        adjust_scanned_elev(real_elev=real_elev, scanned_elev=output_tmp2, new=output_tmp3)
        smooth(scanned_elev=output_tmp3, new=output_elev)
        gcore.run_command('g.remove', rast=output_tmp3)
    else:
        adjust_scanned_elev(real_elev=real_elev, scanned_elev=output_tmp1, new=output_tmp2)
        smooth(scanned_elev=output_tmp2, new=output_elev)
        

    difference(real_elev=real_elev, scanned_elev=output_elev, new=output_diff)

    gcore.run_command('g.remove', rast=output_tmp1)
    gcore.run_command('g.remove', rast=output_tmp2)



def main():
    gcore.use_temp_region()
    import_scan_rinxyz(input_file=r"C:\Users\akratoc\TanGeoMS\output\scan.txt",
                       real_elev='elevation',
                       output_elev='scan',
                       output_diff='diff',
                       mm_resolution=0.002,
                       calib_raster=None)

def cleanup():
    gcore.del_temp_region()


if __name__ == '__main__':
    atexit.register(cleanup)
    sys.exit(main())
