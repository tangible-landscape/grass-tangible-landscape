# -*- coding: utf-8 -*-
"""
Created on Mon Jan 06 16:06:56 2014

@author: akratoc
"""
import os
import grass.script as gscript


def write_matrix(matrix_path):
    res = gscript.parse_command('v.in.kinect', output='dummy', method='mean',
                                    flags='c', quiet=True, overwrite=True)
    if res['calib_matrix'] and len(res['calib_matrix'].split(',')) == 9:
        gscript.message(_("Rotation matrix successfully written to %s") % matrix_path)
    with open(matrix_path, 'w') as f:
        f.write(res['calib_matrix'].strip())
    

if __name__ == '__main__':
    matrix_file_path = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'calib_matrix.txt')
    write_matrix(matrix_path=matrix_file_path)
