#-------------------------------------------------------------------------------
# Name:        module1
# Purpose:
#
# Author:      akratoc
#
# Created:     31/10/2013
# Copyright:   (c) akratoc 2013
# Licence:     <your licence>
#-------------------------------------------------------------------------------

import os
import sys
import atexit
from tempfile import mkstemp

from grass.script import core as gcore

from scan_process import read_from_obj, read_from_ascii, adjust_boundaries, remove_fuzzy_edges

def create_calibration_raster(calib_file, real_elev, output, mm_resolution):
    output_tmp = 'calibration_tmp'
    mm_resolution *= 1000

    fd, temp_path = mkstemp()

    file_name, file_extension = os.path.splitext(calib_file)
    if file_extension.lower() == '.obj':
        lines = read_from_obj(input_file=calib_file, output_file=temp_path)
    else:
        lines = read_from_ascii(input_file=calib_file, output_file=temp_path)
    if not lines:
        print 'ERROR: nothing scanned, try to change min and max Z scanning limits'
        return
    x_min, x_max, y_min, y_max = remove_fuzzy_edges(input_file=temp_path, output_file=temp_path, resolution=mm_resolution)

    gcore.run_command('g.region', n=y_max, s=y_min, e=x_max, w=x_min, res=mm_resolution)

    gcore.run_command('r.in.xyz', separator=" ", input=temp_path, output=output_tmp, overwrite=True)

    os.close(fd)
    os.remove(temp_path)

    adjust_boundaries(real_elev, scanned_elev=output_tmp)
    gcore.run_command('g.region', rast=output_tmp)
    gcore.run_command('r.neighbors', overwrite=True, input=output_tmp, output=output, size=5)
    gcore.run_command('g.remove', rast=output_tmp)



def main():
    import subprocess
    gcore.use_temp_region()
    calibFile = r"C:\Users\akratoc\TanGeoMS\output\calib.txt"
    subprocess.call([r"C:\Users\akratoc\TanGeoMS\Basic\new4\KinectFusionBasics-D2D\Debug\KinectFusionBasics-D2D.exe", calibFile, '20', '0.35', '0.55'])
    create_calibration_raster(calib_file=calibFile,
                              real_elev='lid640ground_bspline2@PERMANENT',
                              output='calibration',
                              mm_resolution=0.002)

def cleanup():
    gcore.del_temp_region()


if __name__ == '__main__':
    atexit.register(cleanup)
    sys.exit(main())