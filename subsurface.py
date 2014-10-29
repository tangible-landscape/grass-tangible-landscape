# -*- coding: utf-8 -*-
"""
Created on Tue Jan 28 12:55:48 2014

@author: akratoc
"""
import os
import subprocess
import tempfile
import shutil
from scan_processing import read_from_ascii, calibrate_points, remove_table, trim_edges_nsew, \
    scale_subsurface_flat, remove_fuzzy_edges, get_environment, adjust_boundaries, remove_temp_regions, \
    bin_surface
from analyses import difference
import numpy as np

from grass.script import core as gcore
from grass.script import raster as grast


def compute_crosssection(real_elev, output_elev, output_cross, voxel, scan_file_path,
                         calib_matrix, zexag, trim_nsew, table_mm, mm_resolution, info_text):
    output_tmp1 = "output_scan_tmp1"
    fd, temp_path = tempfile.mkstemp()
    os.close(fd)
    os.remove(temp_path)
    try:
        read_from_ascii(input_file=scan_file_path, output_file=temp_path)
    except:
        gcore.warning("Failed to read from ascii")
        return
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
    try:
        array = remove_fuzzy_edges(array, mm_resolution, tolerance=0.3)
    except StandardError, e:
        print e
        gcore.warning("Failed to remove fuzzy edges")
        return
    array = trim_edges_nsew(array, trim_nsew)
    gcore.run_command('g.region', rast=real_elev)

    array = scale_subsurface_flat(real_elev, array, zexag, base=table_height, height_mm=37, info_text=info_text)
    # save resulting array
    np.savetxt(temp_path, array, delimiter=" ")

    # import
    tmp_regions = []
    env = get_environment(tmp_regions, n=np.max(array[:, 1]), s=np.min(array[:, 1]), e=np.max(array[:, 0]), w=np.min(array[:, 0]), res=mm_resolution)
    bin_surface(input_file=temp_path, output_raster=output_elev, temporary_raster=output_tmp1, env=env)

    adjust_boundaries(real_elev=real_elev, scanned_elev=output_elev, env=env)
    env = get_environment(tmp_regions, rast=output_elev)
    gcore.write_command('r.colors', map=output_elev, rules='-', stdin="0% 0:66:0\n100% 197:255:138")

#    gcore.run_command('r.colors', map=output_elev, color='elevation')
        

    difference(real_elev=real_elev, scanned_elev=output_elev, new='diff', env=env)

    env = get_environment(tmp_regions, rast3d=voxel, nsres=3, ewres=3)
#    voxels = gcore.read_command('g.mlist', quiet=True, type='rast3d', pattern='interp_2003*', separator=',').strip()
#    for voxel in voxels.split(','):
#        output_cross_ = output_cross + '2' + voxel
    cross_section(output_elev, voxel, output_cross, env=env)
    contours(scanned_elev=output_elev, new='scanned_contours', step=5., env=env)
#    cross_section_fill(output_elev, voxel, output_cross)
#    gcore.run_command('r3.cross.rast', input=voxel, elevation=output_elev, output=output_cross, overwrite=True)

    remove_temp_regions(tmp_regions)
    gcore.run_command('g.remove', rast=output_tmp1, env=env)
    try:
        os.remove(temp_path)
    except:  # WindowsError
        gcore.warning("Failed to remove temporary file {path}".format(path=temp_path))


def contours(scanned_elev, new, env, step=None):
    if not step:
        info = grast.raster_info(scanned_elev)
        step = (info['max'] - info['min']) / 12.
    try:
        if gcore.find_file(new, element='vector')['name']:
            gisenv = gcore.gisenv()
            path_to_vector = os.path.join(gisenv['GISDBASE'], gisenv['LOCATION_NAME'], gisenv['MAPSET'], 'vector', new)
            shutil.rmtree(path_to_vector)
        gcore.run_command('r.contour', flags='t', input=scanned_elev, output=new, maxlevel=0, step=step, env=env)
    except:
        # catching exception when a vector is added to GUI in the same time
        pass


def cross_section(scanned_elev, voxel, new, env):
    gcore.run_command('r3.cross.rast', input=voxel, elevation=scanned_elev, output=new, overwrite=True, env=env)
    gcore.run_command('r.colors', map=new, volume=voxel, env=env)


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
                         zexag=0.7,
                         table_mm=0,
                         edge_mm=[5, 5, 5, 5],
                         mm_resolution=0.001,
                         info_text=[])
