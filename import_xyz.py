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
import numpy as np
from tempfile import mkstemp

from grass.script import core as gcore
from grass.script import raster as grast

from scan_process import read_from_ascii, difference, remove_fuzzy_edges, smooth, calibrate_points, remove_table, scale_z_exag


def import_scan_rinxyz(input_file, real_elev, output_elev, output_diff, mm_resolution, calib_matrix, table_mm):
    output_tmp1 = "output_scan_tmp1"
#    output_tmp2 = "output_scan_tmp2"
#    output_tmp3 = "output_scan_tmp3"
#    mm_resolution *= 1000

    fd, temp_path = mkstemp()
    os.close(fd)
    os.remove(temp_path)
    read_from_ascii(input_file=input_file, output_file=temp_path)

    fh = open(temp_path, 'r')
    array = np.array([map(float, line.split()) for line in fh.readlines()])
    fh.close()

    # calibrate points by given matrix
    array = calibrate_points(array, calib_matrix).T

    # remove underlying table   
    array = remove_table(array, table_mm)

    # remove fuzzy edges
    array, x_min, x_max, y_min, y_max = remove_fuzzy_edges(array, resolution=mm_resolution)

    # scale Z to original and apply exaggeration
    raster_info = grast.raster_info(real_elev)
    array = scale_z_exag(array, raster_info, 3.5)
    
    # save resulting array
    np.savetxt(temp_path, array, delimiter=" ")

    # import
    gcore.run_command('g.region', n=y_max, s=y_min, e=x_max, w=x_min, res=mm_resolution)
    gcore.run_command('r.in.xyz', separator=" ", input=temp_path, output=output_tmp1, overwrite=True)
    os.remove(temp_path)

    info = grast.raster_info(output_tmp1)
    if  math.isnan(info['min']) or math.isnan(info['max']):
        gcore.run_command('g.remove', rast=output_tmp1)
        return    

    gcore.run_command('r.region', map=output_tmp1, raster=real_elev, align=real_elev)
    gcore.run_command('g.region', rast=output_tmp1)

#    if calib_raster:
#        calibrate(scanned_elev=output_tmp1, calib_elev=calib_raster, new=output_tmp2)
#        adjust_scanned_elev(real_elev=real_elev, scanned_elev=output_tmp2, new=output_tmp3)
#        smooth(scanned_elev=output_tmp3, new=output_elev)
#        gcore.run_command('g.remove', rast=output_tmp3)
#    else:
#    adjust_scanned_elev(real_elev=real_elev, scanned_elev=output_tmp1, new=output_tmp2)
    smooth(scanned_elev=output_tmp1, new=output_elev)
    gcore.run_command('r.colors', map=output_elev, color='elevation')
        

    difference(real_elev=real_elev, scanned_elev=output_elev, new=output_diff)

    gcore.run_command('g.remove', rast=output_tmp1)
#    gcore.run_command('g.remove', rast=output_tmp2)



def main():
    import subprocess
    gcore.use_temp_region()
    mesh_path = r"C:\Users\akratoc\TanGeoMS\output\scan.txt"
    subprocess.call([r"C:\Users\akratoc\TanGeoMS\Basic\new4\KinectFusionBasics-D2D\Debug\KinectFusionBasics-D2D.exe", mesh_path, '5', str(0.4), str(0.75)])
    calib_matrix = np.load(r"C:\Users\akratoc\TanGeoMS\output\calib_matrix.npy")
    import_scan_rinxyz(input_file=mesh_path,
                       real_elev='elevation@user1',
                       output_elev='scan',
                       output_diff='diff',
                       mm_resolution=0.001,
                       calib_matrix=calib_matrix,
                       table_mm=4)

def cleanup():
    gcore.del_temp_region()


if __name__ == '__main__':
    atexit.register(cleanup)
    sys.exit(main())
