# -*- coding: utf-8 -*-
"""
Created on Mon Jan 06 16:06:56 2014

@author: akratoc
"""
import os
import subprocess
import numpy as np
import tempfile
from scan_processing import get_calibration_matrix, read_from_ascii


def write_matrix(matrix_path, min_z, max_z):
    fd_mesh, mesh_path = tempfile.mkstemp()
    os.close(fd_mesh)
    os.remove(mesh_path)
    print "MEASURING AND CREATING MESH..."
    subprocess.call([os.path.join(os.path.dirname(os.path.realpath(__file__)), 'kinect', 'scan_once', 'KinectFusionBasics-D2D.exe'),
                     mesh_path, '20', str(min_z), str(max_z), '256 ', '256'])
    fd, temp_path = tempfile.mkstemp()
    os.close(fd)
    os.remove(temp_path)
    read_from_ascii(input_file=mesh_path, output_file=temp_path)
    os.remove(mesh_path)

    fh = open(temp_path, 'r')
    array = np.array([map(float, line.split()) for line in fh.readlines()])
    fh.close()
    os.remove(temp_path)
    print "COMPUTING CALIBRATION MATRIX..."
    R = get_calibration_matrix(array)
    np.save(matrix_path, R)
    print "MATRIX SAVED TO " + str(matrix_path)




if __name__ == '__main__':
    matrix_file_path = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'calib_matrix.npy')
    write_matrix(matrix_path=matrix_file_path, min_z=0.5, max_z=1.0)
