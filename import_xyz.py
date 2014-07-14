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
import numpy as np
from tempfile import mkstemp, gettempdir

from grass.script import core as gcore
from grass.script import raster as grast

from scan_processing import  get_environment, remove_temp_regions, read_from_ascii, adjust_boundaries, remove_fuzzy_edges, calibrate_points, remove_table, scale_z_exag
from analyses import smooth, difference, flowacc, max_curv, simwe, contours, landform, geomorphon, usped, slope



def import_scan_rinxyz(input_file, real_elev, output_elev, output_diff, mm_resolution, calib_matrix, table_mm, zexag):
    output_tmp1 = "output_scan_tmp1"

    fd, temp_path = mkstemp()
    os.close(fd)
    os.remove(temp_path)
    try:
        read_from_ascii(input_file=input_file, output_file=temp_path)
    except:
        return

    fh = open(temp_path, 'r')
    array = np.array([map(float, line.split()) for line in fh.readlines()])
    fh.close()

    # calibrate points by given matrix
    array = calibrate_points(array, calib_matrix).T

    # remove underlying table
    try:
        array = remove_table(array, table_mm)
    except StandardError, e:
        print e
        return

    # remove fuzzy edges
    try:
        array = remove_fuzzy_edges(array, resolution=mm_resolution, tolerance=0.3)
    except StandardError, e:
        print e
        return

    # scale Z to original and apply exaggeration
    raster_info = grast.raster_info(real_elev)
    try:
        array = scale_z_exag(array, raster_info, zexag)
    except StandardError, e:
        print e
        return

    # save resulting array
    np.savetxt(temp_path, array, delimiter=" ")

    # import
    if array.shape[0] < 2000:
        return

    tmp_regions = []
    env = get_environment(tmp_regions, n=np.max(array[:, 1]), s=np.min(array[:, 1]), e=np.max(array[:, 0]), w=np.min(array[:, 0]), res=mm_resolution)
    gcore.run_command('r.in.xyz', separator=" ", input=temp_path, output=output_tmp1, overwrite=True, env=env)
    try:
        os.remove(temp_path)
    except:  # WindowsError
        gcore.warning("Failed to remove temporary file {path}".format(path=temp_path))

    info = grast.raster_info(output_tmp1)
    if info['min'] is None or info['max'] is None or np.isnan(info['min']) or np.isnan(info['max']):
        gcore.run_command('g.remove', rast=output_tmp1)
        return

    adjust_boundaries(real_elev=real_elev, scanned_elev=output_tmp1, env=env)
    env = get_environment(tmp_regions, rast=output_tmp1)
    smooth(scanned_elev=output_tmp1, new=output_elev, env=env)
    gcore.run_command('r.colors', map=output_elev, color='elevation', env=env)


########### analyses ##################################
#    difference(real_elev=real_elev, scanned_elev=output_elev, new=output_diff, env=env)
#    contours(output_elev, new='contours_scanned', step=2, env=env)
#    flowacc(output_elev, new='flowacc', env=env)
#    max_curv(output_elev, new='maxic', env=env)
#    landform(output_elev, new='landforms', env=env)
#    geomorphon(output_elev, new='geomorphon', env=env)
#    simwe(output_elev, slope='slope', aspect='aspect', depth='depth', env=env)
#    usped(output_elev, k_factor='soils_Kfactor', c_factor='cfactorbare_1m', flowacc='flowacc', slope='slope', aspect='aspect', new='erdep', env=env)
#    usped(output_elev, k_factor='soils_Kfactor', c_factor='c_factor_0_5', flowacc='flowacc', slope='slope', aspect='aspect', new='erdep05', env=env)
#    slope(output_elev, new='slope', env=env)
########################################################

    gcore.run_command('g.remove', rast=output_tmp1, env=env)
    remove_temp_regions(tmp_regions)


def main():
    import subprocess
#    gcore.use_temp_region()
    mesh_path = os.path.join(os.path.realpath(gettempdir()), 'kinect_scan.txt')

    kinect_app = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'kinect', 'scan_once', 'KinectFusionBasics-D2D.exe')
    subprocess.call([kinect_app, mesh_path, '5', str(0.4), str(0.75)])
    calib_matrix = np.load(os.path.join(os.path.dirname(os.path.realpath(__file__)), 'calib_matrix.npy'))
    import_scan_rinxyz(input_file=mesh_path,
                       real_elev='elevation@user1',
                       output_elev='scan',
                       output_diff='diff',
                       mm_resolution=0.001,
                       calib_matrix=calib_matrix,
                       table_mm=4, zexag=3)

def cleanup():
    print 'cleanup'


if __name__ == '__main__':
    atexit.register(cleanup)
    sys.exit(main())
