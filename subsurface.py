# -*- coding: utf-8 -*-
"""
Created on Tue Jan 28 12:55:48 2014

@author: akratoc
"""
import os
import subprocess
import tempfile
from scan_process import read_from_ascii, calibrate_points, remove_table, trim_edges_nsew, scale_subsurface_flat, difference, smooth
import numpy as np

from grass.script import core as gcore
#from grass.script import raster as grast


def compute_crosssection(real_elev, output_elev, output_diff, output_cross, voxel, scan_file_path, calib_matrix, zexag, table_mm, edge_mm, mm_resolution):
    output_tmp1 = "output_scan_tmp1"
    fd, temp_path = tempfile.mkstemp()
    os.close(fd)
    os.remove(temp_path)
    read_from_ascii(input_file=scan_file_path, output_file=temp_path)

    fh = open(temp_path, 'r')
    array = np.array([map(float, line.split()) for line in fh.readlines()])
    fh.close()
    os.remove(temp_path)
    
    # calibrate points by given matrix
    array = calibrate_points(array, calib_matrix).T
    table_height = np.percentile(array[:, 2], 10)
    # remove underlying table   
    array = remove_table(array, table_mm)
    
    # cut edges
    array = trim_edges_nsew(array, edge_mm)
    gcore.run_command('g.region', rast=real_elev)
    array = scale_subsurface_flat(real_elev, array, zexag, base=table_height, height_mm=32)
    
    # save resulting array
    np.savetxt(temp_path, array, delimiter=" ")

    # import
    gcore.run_command('g.region', n=np.max(array[:, 1]), s=np.min(array[:, 1]), e=np.max(array[:, 0]), w=np.min(array[:, 0]), res=mm_resolution)
    gcore.run_command('r.in.xyz', separator=" ", input=temp_path, output=output_tmp1, overwrite=True)
    os.remove(temp_path)

    gcore.run_command('r.region', map=output_tmp1, raster=real_elev, align=real_elev)
    gcore.run_command('g.region', rast=output_tmp1)
    
    smooth(scanned_elev=output_tmp1, new=output_elev)
    gcore.write_command('r.colors', map=output_elev, rules='-', stdin="0% 0:66:0\n100% 197:255:138")

#    gcore.run_command('r.colors', map=output_elev, color='elevation')
        

    difference(real_elev=real_elev, scanned_elev=output_elev, new=output_diff)

    gcore.run_command('g.remove', rast=output_tmp1)
    
    gcore.run_command('g.region', rast3d=voxel, nsres=3, ewres=3)
#    voxels = gcore.read_command('g.mlist', quiet=True, type='rast3d', pattern='interp_2003*', separator=',').strip()
#    for voxel in voxels.split(','):
#        output_cross_ = output_cross + '2' + voxel
    cross_section(output_elev, voxel, output_cross)
#    cross_section_fill(output_elev, voxel, output_cross)
#    gcore.run_command('r3.cross.rast', input=voxel, elevation=output_elev, output=output_cross, overwrite=True)


def cross_section(scanned_elev, voxel, new):
    gcore.run_command('r3.cross.rast', input=voxel, elevation=scanned_elev, output=new, overwrite=True)
    gcore.run_command('r.colors', map=new, volume=voxel)


if __name__ == '__main__':
    scan_file_path = r"C:\Users\akratoc\TanGeoMS\output\scan.txt"
    min_z, max_z = 0.5, 1.
    subprocess.call([r"C:\Users\akratoc\TanGeoMS\Basic\new4\KinectFusionBasics-D2D\Debug\KinectFusionBasics-D2D.exe", scan_file_path, '5', str(min_z), str(max_z)])
    calib_matrix = np.load(r"C:\Users\akratoc\TanGeoMS\output\calib_matrix.npy")
    compute_crosssection(real_elev='dummy',
                         output_elev='scan',
                         output_diff='diff',
                         output_cross='cross',
                         voxel='interp_2002_08_25',
                         scan_file_path=scan_file_path,
                         calib_matrix=calib_matrix,
                         zexag=1,
                         table_mm=0,
                         edge_mm=[5, 5, 5, 5],
                         mm_resolution=0.001)
