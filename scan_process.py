#-------------------------------------------------------------------------------
# Name:        scan_process
# Purpose:
#
# Author:      akratoc
#
# Created:     31/10/2013
# Copyright:   (c) akratoc 2013
# Licence:     <your licence>
#-------------------------------------------------------------------------------

import numpy as np

from grass.script import core as gcore
from grass.script import raster as grast


###################### numpy ####################################

def get_calibration_matrix(array):
    A = np.vstack([array[:, 0], array[:, 1], np.ones(len(array[:, 1]))]).T
    a, b, c = np.linalg.lstsq(A, array[:, 2])[0]
    V1 = np.array([a, b, -1])
    V2 = np.array([0, 0, -1])

    u = unit_vector(np.cross(V1, V2))
    angle = angle_between(V1, V2)
    print "Point cloud deviation angle [degrees]: " + str(angle * 180 / np.pi)

    U2 = np.array([[0, -u[2], u[1]],
                   [u[2], 0, -u[0]],
                   [-u[1], u[0], 0]])

    # Rodrigues' Rotation Formula (http://mathworld.wolfram.com/RodriguesRotationFormula.html)
    R = np.identity(3) + U2 * np.sin(angle) + np.linalg.matrix_power(U2, 2) * (1 - np.cos(angle))

    return R


def calibrate_points(array, calib_matrix):
    return np.dot(calib_matrix, array)


def unit_vector(vector):
    """ Returns the unit vector of the vector.  """
    return vector / np.linalg.norm(vector)


def angle_between(v1, v2):
    """ Returns the angle in radians between vectors 'v1' and 'v2'::

    >>> angle_between((1, 0, 0), (0, 1, 0))
    1.5707963267948966
    >>> angle_between((1, 0, 0), (1, 0, 0))
    0.0
    >>> angle_between((1, 0, 0), (-1, 0, 0))
    3.141592653589793
    """
    v1_u = unit_vector(v1)
    v2_u = unit_vector(v2)
    angle = np.arccos(np.dot(v1_u, v2_u))
    if np.isnan(angle):
        if (v1_u == v2_u).all():
            return 0.0
        else:
            return np.pi
    return angle


def remove_fuzzy_edges(array, resolution, tolerance=0.8):
    bins_n = (np.max(array[:, 0]) - np.min(array[:, 0])) / resolution
    H, yedges, xedges = np.histogram2d(-array[:, 1], array[:, 0], bins=(bins_n, bins_n))

#    extent = [xedges[0], xedges[-1], yedges[0], yedges[-1]]
#    import matplotlib.pyplot as plt
#    np.clip(H, 0, 1, H)
#    plt.ion()
#    plt.imshow(H, extent=extent, interpolation='nearest', origin='upper')
#    plt.colorbar()
#    
#    plt.show()


    np.clip(H, 0, 1, H)

    default_x = max(np.sum(H[int(H.shape[0]/2), :]), np.sum(H[int(H.shape[0]/2) + 1, :]))
    
    default_y = max(np.sum(H[:, int(H.shape[1]/2)]), np.sum(H[:, int(H.shape[1]/2) + 1]))
    
    row = 1

    while np.sum(H[-row, :]) / float(default_y) < tolerance:
        row += 1
    limit_y_s = yedges[row]


    row = 0
    while np.sum(H[row, :]) / float(default_y) < tolerance:
        row += 1
    limit_y_n = yedges[-row]

    col = 1
    while np.sum(H[:, -col]) / float(default_x) < tolerance:
        col += 1
    limit_x_e = xedges[-col]

    col = 0
    while np.sum(H[:, col]) / float(default_x) < tolerance:
        col += 1

    limit_x_w = xedges[col]

#    array = array[array[:, 0] <= limit_x_e]
#    array = array[array[:, 0] >= limit_x_w]
#    array = array[array[:, 1] <= -limit_y_s]
#    array = array[array[:, 1] >= -limit_y_n]
#    bins_n = (np.max(array[:, 0]) - np.min(array[:, 0])) / resolution
#    H, yedges, xedges = np.histogram2d(-array[:, 1], array[:, 0], bins=(bins_n, bins_n))
#    np.clip(H, 0, 1, H)
#    extent = [xedges[0], xedges[-1], yedges[0], yedges[-1]]
#    plt.imshow(H, extent=extent, interpolation='nearest', origin='upper')
#    plt.colorbar()
#    plt.draw()

    #np.savetxt(output_file, array, delimiter=" ")
#    print limit_x_w, limit_x_e, limit_y_s, limit_y_n
#    print np.min(array[:, 0]), np.max(array[:, 0]), np.min(array[:, 1]), np.max(array[:, 1])
    return limit_x_w, limit_x_e, -limit_y_n, -limit_y_s
#    return np.min(array[:, 0]), np.max(array[:, 0]), np.min(array[:, 1]), np.max(array[:, 1])


###################### GRASS ####################################

def adjust_boundaries(real_elev, scanned_elev):
    gcore.run_command('r.region', map=scanned_elev, raster=real_elev, align=real_elev)


def adjust_scanned_elev(real_elev, scanned_elev, new):
    res = gcore.read_command('r.regression.line', map1=scanned_elev,
    map2=real_elev, flags='g')
    res = gcore.parse_key_val(res, val_type=float)
    
    expression = "{new} = {a} + {b} * {elev}".format(new=new, a=res['a'], b=res['b'], elev=scanned_elev)
    grast.mapcalc(expression, overwrite=True)

def difference(real_elev, scanned_elev, new):
    info = grast.raster_info(real_elev)
#    expression = "{new} = ({real_elev} - {scanned_elev}) / ({max} - {min}) * 100".format(new=new, real_elev=real_elev,
    expression = "{new} = {real_elev} - {scanned_elev}".format(new=new, real_elev=real_elev,
                 scanned_elev=scanned_elev, max=info['max'], min=info['min'])
    grast.mapcalc(expression, overwrite=True)
    gcore.run_command('r.colors', map=new, color='differences', flags='n')


def read_from_obj(input_file, output_file, rotate_180=True):
    fh_input = open(input_file, 'r')
    fh_output = open(output_file, 'w')

    count = 0
    for line in fh_input.readlines():
        count += 1
        if 'v' in line:
            if 'vn' not in line:
                line_list = line.split() # convert to a list
                line_list.remove("v") # remove the string "v"
                x, y, z = map(float, line_list)
                if rotate_180:
                    fh_output.write("{x} {y} {z}\n".format(x=-x * 1000, y=-y * 1000, z=z * 1000))
                else:
                    fh_output.write("{x} {y} {z}\n".format(x=x * 1000, y=y * 1000, z=z * 1000))

    fh_input.close()
    fh_output.close()
    if count < 100:
        print 'WARNING: number of lines in input file is only {}'.format(count)
    return count


def read_from_ascii(input_file, output_file, rotate_180=True):
    fh_input = open(input_file, 'r')
    fh_output = open(output_file, 'w')

    count = 0
    for line in fh_input.readlines():
        count += 1
        x, y, z = map(float, line.split())
        if rotate_180:
            fh_output.write("{x} {y} {z}\n".format(x=-x * 1000, y=-y * 1000, z=z * 1000))
        else:
            fh_output.write("{x} {y} {z}\n".format(x=x * 1000, y=y * 1000, z=z * 1000))

    fh_input.close()
    fh_output.close()
    if count < 100:
        print 'WARNING: number of lines in input file is only {}'.format(count)
    return count

def calibrate(scanned_elev, calib_elev, new):
    expression = "{new} = {scanned_elev} - {calib_elev}".format(new=new, calib_elev=calib_elev, scanned_elev=scanned_elev)
    grast.mapcalc(expression, overwrite=True)

def smooth(scanned_elev, new):
    gcore.run_command('r.neighbors', input=scanned_elev, output=new, size=5, overwrite=True)


