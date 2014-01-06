# -*- coding: utf-8 -*-
"""
Created on Mon Jan 06 16:06:56 2014

@author: akratoc
"""
import os
import subprocess
import numpy as np
import tempfile
from scan_process import get_calibration_matrix, read_from_ascii


def write_matrix(mesh_path, matrix_path, min_z, max_z):
    print "MEASURING AND CREATING MESH..."
    subprocess.call([r"C:\Users\akratoc\TanGeoMS\Basic\new4\KinectFusionBasics-D2D\Debug\KinectFusionBasics-D2D.exe", mesh_path, '5', str(min_z), str(max_z)])
    fd, temp_path = tempfile.mkstemp()
    os.close(fd)
    os.remove(temp_path)
    read_from_ascii(input_file=mesh_path, output_file=temp_path)

    fh = open(temp_path, 'r')
    array = np.array([map(float, line.split()) for line in fh.readlines()])
    fh.close()
    os.remove(temp_path)
    print "COMPUTING CALIBRATION MATRIX..."
    R = get_calibration_matrix(array)
    np.save(matrix_path, R)
    print "MATRIX SAVED TO " + str(matrix_path)

    # just to test
    print np.load(matrix_path + '.npy')
    
    
    

if __name__ == '__main__':
    matrix_file_path = r"C:\Users\akratoc\TanGeoMS\output\calib_matrix"
    mesh_file_path = r"C:\Users\akratoc\TanGeoMS\output\table"
    write_matrix(mesh_path=mesh_file_path, matrix_path=matrix_file_path, min_z=0.5, max_z=1.0)