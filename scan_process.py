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
    return np.dot(calib_matrix, array.T)


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

def remove_table(array, height):
    """Removes points under the model (table).
    height is in mm.    
    """
    z = array[:, 2] * 1000
    min_z = np.min(z)
    max_z = np.max(z)
    range_mm = int(max_z - min_z)
    hist_values, bin_edges = np.histogram(z, bins=range_mm)
    max_idx = np.argmax(hist_values)
    minimas = (np.diff(np.sign(np.diff(smooth_signal(hist_values, window_len=5)))) > 0).nonzero()[0] + 1

#    from pylab import plot, show
#    plot(list(smooth_signal(hist_values, window_len=3)))
#    show()
   
    min_z += minimas[minimas > max_idx][0] + height
    array = array[z >= min_z]
    return array
    
    
def scale_z_exag(array, raster_info, zexag):
    """Change z range to match z-exag"""
    old_min_z = np.min(array[:, 2])
#    old_max_z = np.max(array[:, 2])
    old_min_x = np.min(array[:, 0])
    old_max_x = np.max(array[:, 0])
    old_min_y = np.min(array[:, 1])
    old_max_y = np.max(array[:, 1])
    
    ns_scale = (raster_info['north'] - raster_info['south']) / (old_max_y - old_min_y)
    ew_scale = (raster_info['east'] - raster_info['west'] ) / (old_max_x - old_min_x)
    hor_scale = (ns_scale + ew_scale) / 2
    scale = float(hor_scale) / zexag
    print "SCALE: " + str(hor_scale)
    print "Z-EXAGGERATION: " + str(zexag)
    print "1 cm in height ~ {} m".format(0.01 * scale)
    array[:, 2] = array[:, 2] * scale + raster_info['min'] - old_min_z * scale
    return array


def scale_z_raster(array, raster_info):
    """Change z range to match raster map range"""
    old_min_z = np.min(array[:, 2])
    old_max_z = np.max(array[:, 2])    
    old_range = old_max_z - old_min_z
    new_range = raster_info['max'] - raster_info['min']
    array[:, 2] = (((array[:, 2] - old_min_z) * new_range) / old_range) + raster_info['min']
    return array
        

def remove_fuzzy_edges(array, resolution, tolerance=0.5):
    bins_n = (np.max(array[:, 0]) - np.min(array[:, 0])) / resolution
    H, yedges, xedges = np.histogram2d(-array[:, 1], array[:, 0], bins=(bins_n, bins_n))
    
#    extent = [xedges[0], xedges[-1], yedges[0], yedges[-1]]
#    import matplotlib.pyplot as plt
#    np.clip(H, 0, 1, H)
#    plt.ion()
#    plt.imshow(H, extent=extent, interpolation='nearest', origin='upper')
#    plt.colorbar()
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

    array = array[array[:, 0] <= limit_x_e]
    array = array[array[:, 0] >= limit_x_w]
    array = array[array[:, 1] <= -limit_y_s]
    array = array[array[:, 1] >= -limit_y_n]
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
    return array, limit_x_w, limit_x_e, -limit_y_n, -limit_y_s
#    return np.min(array[:, 0]), np.max(array[:, 0]), np.min(array[:, 1]), np.max(array[:, 1])


def trim_edges(array, edge_mm):
    edge_mm /= 1000.
    array = array[array[:, 0] <= (np.max(array[:, 0]) - edge_mm)]
    array = array[array[:, 0] >= np.min(array[:, 0]) + edge_mm]
    array = array[array[:, 1] <= np.max(array[:, 1]) - edge_mm]
    array = array[array[:, 1] >= np.min(array[:, 1]) + edge_mm]
    return array


def scale_by_corners(real_elev, array, zexag, toler_mm):
    raster_info = grast.raster_info(real_elev)
    res = (raster_info['nsres'] + raster_info['ewres']) / 2.0
    coordinates = (raster_info['west'] + res / 2.0, raster_info['south'] + res / 2.0)  # WS
    what = grast.raster_what(real_elev, coordinates)
    value = float(what[0][real_elev]['value'])

    old_min_x = np.min(array[:, 0])
    old_max_x = np.max(array[:, 0])
    old_min_y = np.min(array[:, 1])
    old_max_y = np.max(array[:, 1])
    corner = array[array[:, 0] <= old_min_x + toler_mm]
    corner = corner[corner[:, 1] <= old_min_y + toler_mm]
    avg_value = np.average(corner[:, 2])

    ns_scale = (raster_info['north'] - raster_info['south']) / (old_max_y - old_min_y)
    ew_scale = (raster_info['east'] - raster_info['west'] ) / (old_max_x - old_min_x)
    hor_scale = (ns_scale + ew_scale) / 2
    scale = float(hor_scale) / zexag

    array[:, 2] = array[:, 2] * scale + value - avg_value * scale + 0.001*scale

    print "SCALE: " + str(hor_scale)
    print "Z-EXAGGERATION: " + str(zexag)
    print "1 cm in height ~ {} m".format(0.01 * scale)

    return array


def smooth_signal(x, window_len=11, window='hanning'):
    """smooth the data using a window with requested size.
    
    This method is based on the convolution of a scaled window with the signal.
    The signal is prepared by introducing reflected copies of the signal 
    (with the window size) in both ends so that transient parts are minimized
    in the begining and end part of the output signal.
    
    input:
        x: the input signal 
        window_len: the dimension of the smoothing window; should be an odd integer
        window: the type of window from 'flat', 'hanning', 'hamming', 'bartlett', 'blackman'
            flat window will produce a moving average smoothing.

    output:
        the smoothed signal
        
    example:

    t=linspace(-2,2,0.1)
    x=sin(t)+randn(len(t))*0.1
    y=smooth(x)
    
    see also: 
    
    numpy.hanning, numpy.hamming, numpy.bartlett, numpy.blackman, numpy.convolve
    scipy.signal.lfilter
 
    TODO: the window parameter could be the window itself if an array instead of a string
    NOTE: length(output) != length(input), to correct this: return y[(window_len/2-1):-(window_len/2)] instead of just y.
    """

    if x.ndim != 1:
        raise ValueError, "smooth only accepts 1 dimension arrays."

    if x.size < window_len:
        raise ValueError, "Input vector needs to be bigger than window size."


    if window_len<3:
        return x


    if not window in ['flat', 'hanning', 'hamming', 'bartlett', 'blackman']:
        raise ValueError, "Window is on of 'flat', 'hanning', 'hamming', 'bartlett', 'blackman'"


    s=np.r_[x[window_len-1:0:-1],x,x[-1:-window_len:-1]]

    if window == 'flat': #moving average
        w=np.ones(window_len,'d')
    else:
        w=eval('np.'+window+'(window_len)')

    y=np.convolve(w/w.sum(),s,mode='valid')
    return y

###################### GRASS ####################################

def adjust_boundaries(real_elev, scanned_elev):
    gcore.run_command('r.region', map=scanned_elev, raster=real_elev, align=real_elev)


def adjust_scanned_elev(real_elev, scanned_elev, new):
    res = gcore.read_command('r.regression.line', map1=scanned_elev,
    map2=real_elev, flags='g')
    res = gcore.parse_key_val(res, val_type=float)
    
    expression = "{new} = {a} + {b} * {elev}".format(new=new, a=res['a'], b=res['b'], elev=scanned_elev)
    grast.mapcalc(expression, overwrite=True)
    gcore.run_command('r.colors', map=new, color='elevation')

def difference(real_elev, scanned_elev, new):
    info = grast.raster_info(real_elev)
#    expression = "{new} = ({real_elev} - {scanned_elev}) / ({max} - {min}) * 100".format(new=new, real_elev=real_elev,
    expression = "{new} = {scanned_elev} - {real_elev}".format(new=new, real_elev=real_elev,
                 scanned_elev=scanned_elev, max=info['max'], min=info['min'])
    grast.mapcalc(expression, overwrite=True)
    gcore.run_command('r.colors', map=new, color='differences')


def read_from_obj(input_file, output_file, rotate_180=True):
    fh_input = open(input_file, 'r')
    fh_output = open(output_file, 'w')

    scale = 1
    count = 0
    for line in fh_input.readlines():
        count += 1
        if 'v' in line:
            if 'vn' not in line:
                line_list = line.split() # convert to a list
                line_list.remove("v") # remove the string "v"
                x, y, z = map(float, line_list)
                if rotate_180:
                    fh_output.write("{x} {y} {z}\n".format(x=-x * scale, y=-y * scale, z=z * scale))
                else:
                    fh_output.write("{x} {y} {z}\n".format(x=x * scale, y=y * scale, z=z * scale))

    fh_input.close()
    fh_output.close()
    if count < 100:
        print 'WARNING: number of lines in input file is only {}'.format(count)
    return count


def read_from_ascii(input_file, output_file, rotate_180=True):
    fh_input = open(input_file, 'r')
    fh_output = open(output_file, 'w')

    scale = 1
    count = 0
    for line in fh_input.readlines():
        count += 1
        x, y, z = map(float, line.split())
        if rotate_180:
            fh_output.write("{x} {y} {z}\n".format(x=-x * scale, y=-y * scale, z=z * scale))
        else:
            fh_output.write("{x} {y} {z}\n".format(x=x * scale, y=y * scale, z=z * scale))

    fh_input.close()
    fh_output.close()
    if count < 100:
        print 'WARNING: number of lines in input file is only {}'.format(count)
    return count

def calibrate(scanned_elev, calib_elev, new):
    expression = "{new} = {scanned_elev} - {calib_elev}".format(new=new, calib_elev=calib_elev, scanned_elev=scanned_elev)
    grast.mapcalc(expression, overwrite=True)

def smooth(scanned_elev, new):
    gcore.run_command('r.neighbors', input=scanned_elev, output=new, size=9, overwrite=True)

def flowacc(scanned_elev, new):
    gcore.run_command('r.flow', elevation=scanned_elev, flowaccumulation=new, overwrite=True)
