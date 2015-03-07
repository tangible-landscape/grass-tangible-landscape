# -*- coding: utf-8 -*-
"""
@brief Functions for processing scan

This program is free software under the GNU General Public License
(>=v2). Read the file COPYING that comes with GRASS for details.

@author: Anna Petrasova (akratoc@ncsu.edu)
"""
import numpy as np
import os
import uuid
import shutil

from grass.script import core as gcore
from grass.script import raster as grast
from grass.exceptions import CalledModuleError


###################### numpy ###########################
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


#-------------- calibration ----------------------------
def get_calibration_matrix(array):
    A = np.vstack([array[:, 0], array[:, 1], np.ones(len(array[:, 1]))]).T
    a, b, c = np.linalg.lstsq(A, array[:, 2])[0]
    V1 = np.array([a, b, -1])
    V2 = np.array([0, 0, -1])

    u = unit_vector(np.cross(V1, V2))
    angle = angle_between(V1, V2)
    print "Point cloud deviation angle [degrees]: " + str(angle * 180 / np.pi)
    if (angle * 180 / np.pi) > 2.:
        print "The deviation angle is too large please adjust Kinect manually and repeat."

    U2 = np.array([[0, -u[2], u[1]],
                   [u[2], 0, -u[0]],
                   [-u[1], u[0], 0]])

    # Rodrigues' Rotation Formula (http://mathworld.wolfram.com/RodriguesRotationFormula.html)
    R = np.identity(3) + U2 * np.sin(angle) + np.linalg.matrix_power(U2, 2) * (1 - np.cos(angle))

    return R


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


def calibrate_points(array, calib_matrix):
    return np.dot(calib_matrix, array.T)


def rotate_points(array, angle):
    """Rotates point cloud by angle in degrees, counterclockwise"""
    angle = angle / 180. *np.pi
    rotmat = np.array([[np.cos(angle), -np.sin(angle), 0], [np.sin(angle), np.cos(angle), 0], [0, 0, 1]])
    array = np.dot(rotmat, array.T).T
    return array


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

    min_z = np.min(z)
    min_z += minimas[minimas > max_idx][0] + height
    array = array[z >= min_z]
    return array


def scale_z_exag(array, raster_info, zexag, info_text):
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
    info_text.append("Model scale 1:{0:.0f}".format(hor_scale))
    info_text.append("1 cm in height ~ {0:.1f} m".format(0.01 * scale))
    array[:, 2] = array[:, 2] * scale + raster_info['min'] - old_min_z * scale
    return array, hor_scale


def scale_z_raster(array, raster_info):
    """Change z range to match raster map range"""
    old_min_z = np.min(array[:, 2])
    old_max_z = np.max(array[:, 2])
    old_range = old_max_z - old_min_z
    new_range = raster_info['max'] - raster_info['min']
    array[:, 2] = (((array[:, 2] - old_min_z) * new_range) / old_range) + raster_info['min']
    return array


def scale_subsurface_flat(real_elev, array, zexag, base, height_mm, info_text):
    raster_info = grast.raster_info(real_elev)
    old_min_x = np.min(array[:, 0])
    old_max_x = np.max(array[:, 0])
    old_min_y = np.min(array[:, 1])
    old_max_y = np.max(array[:, 1])
    ns_scale = (raster_info['north'] - raster_info['south']) / (old_max_y - old_min_y)
    ew_scale = (raster_info['east'] - raster_info['west'] ) / (old_max_x - old_min_x)
    hor_scale = (ns_scale + ew_scale) / 2
    scale = float(hor_scale) / zexag
    real_height = base + height_mm/1000.

    array[:, 2] = array[:, 2] * scale - (real_height * scale - raster_info['max'])

    info_text.append("Model scale 1:{0:.0f}".format(hor_scale))
    info_text.append("1 cm in height ~ {0:.1f} m".format(0.01 * scale))

    return array


def remove_fuzzy_edges(array, resolution, tolerance=0.1):
    """Function trims edges from rectangular model to get rid of noise on the edges.
    Warning: use with caution when model is not rectangular

    @param array input array of data, array[:, 0] is x, array[:, 1] is y
    @param resolution for binning
    @param tolerance tolerance 0 to 1, lower tol. is more strict
    """
    intolerance = 1 - tolerance
    maxx, minx = np.max(array[:, 0]), np.min(array[:, 0])
    maxy, miny = np.max(array[:, 1]), np.min(array[:, 1])
    bins_nx = (maxx - minx) / resolution
    bins_ny = (maxy - miny) / resolution

    # binning
    H, yedges, xedges = np.histogram2d(-array[:, 1], array[:, 0], bins=(bins_ny, bins_nx))
    np.clip(H, 0, 1, H)

    # get max values for model width and height to compare it with the edges
    sum_x = np.sum(H, axis=1)
    default_x = np.percentile(sum_x[np.nonzero(sum_x)], 50)
    sum_y = np.sum(H, axis=0)
    default_y = np.percentile(sum_y[np.nonzero(sum_y)], 50)

    # determine the limits
    row = 1
    while np.sum(H[-row, :]) / float(default_y) < intolerance:
        row += 1
    limit_y_s = miny + (yedges[row - 1] - yedges[0])

    row = 0
    while np.sum(H[row, :]) / float(default_y) < intolerance:
        row += 1
    limit_y_n = maxy - (yedges[-1] - yedges[-row - 1])

    col = 1
    while np.sum(H[:, -col]) / float(default_x) < intolerance:
        col += 1
    limit_x_e = maxx - (xedges[-1] - xedges[-col])

    col = 0
    while np.sum(H[:, col]) / float(default_x) < intolerance:
        col += 1
    limit_x_w = minx + (xedges[col] - xedges[0])

    # trim array
    array = array[array[:, 0] <= limit_x_e]
    array = array[array[:, 0] >= limit_x_w]
    array = array[array[:, 1] >= limit_y_s]
    array = array[array[:, 1] <= limit_y_n]

    return array


def trim_edges_nsew(array, nsew):
    nsew = [direct/1000. for direct in nsew]
    array = array[array[:, 0] <= (np.max(array[:, 0]) - nsew[2])]
    array = array[array[:, 0] >= np.min(array[:, 0]) + nsew[3]]
    array = array[array[:, 1] <= np.max(array[:, 1]) - nsew[0]]
    array = array[array[:, 1] >= np.min(array[:, 1]) + nsew[1]]
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
def get_environment(tmp_regions, **kwargs):
    """!Returns environment for running modules.
    All modules for which region is important should
    pass this environment into run_command or similar.

    @param tmp_regions a list of temporary regions
    @param kwargs arguments for g.region

    @return environment as a dictionary
    """
    name = str(uuid.uuid4())[:8]
    gcore.run_command('g.region', flags='u', save=name, **kwargs)
    tmp_regions.append(name)
    env = os.environ.copy()
    env['WIND_OVERRIDE'] = name
    env['GRASS_OVERWRITE'] = '1'
    env['GRASS_VERBOSE'] = '0'
    env['GRASS_MESSAGE_FORMAT'] = 'standard'
    if 'GRASS_REGION' in env:
        del env['GRASS_REGION']
    return env


def remove_vector(name, deleteTable=False):
    """Helper function to workaround problem with deleting vectors"""
    gisenv = gcore.gisenv()
    path_to_vector = os.path.join(gisenv['GISDBASE'], gisenv['LOCATION_NAME'], gisenv['MAPSET'], 'vector', name)
    if deleteTable:
        try:
            gcore.run_command('db.droptable', table=name, flags='f')
        except CalledModuleError:
            pass
    if os.path.exists(path_to_vector):
        try:
            shutil.rmtree(path_to_vector)
        except WindowsError:
            pass


def remove_temp_regions(regions):
    """!Removes temporary regions."""
    gisenv = gcore.gisenv()
    path_to_regions = os.path.join(gisenv['GISDBASE'], gisenv['LOCATION_NAME'], gisenv['MAPSET'], 'windows')
    for region in regions:
        os.remove(os.path.join(path_to_regions, region))


def adjust_boundaries(real_elev, scanned_elev, env):
    gcore.run_command('r.region', map=scanned_elev, raster=real_elev, align=real_elev, env=env)


def interpolate_surface(input_file, output_raster, temporary_vector, env):
    remove_vector(temporary_vector)
    gcore.run_command('v.in.ascii', flags='ztb', z=3, separator=" ", input=input_file, output=temporary_vector, overwrite=True, env=env)
    gcore.run_command('v.surf.rst', input=temporary_vector, tension=25, segmax=100, dmin=0.003, smooth=5, npmin=150,
                      elevation=output_raster, overwrite=True, env=env)


def bin_surface(input_file, output_raster, temporary_raster, env):
    gcore.run_command('r.in.xyz', separator=" ", input=input_file, method='max',
                      output=temporary_raster, overwrite=True, env=env)
    gcore.run_command('r.neighbors', input=temporary_raster, output=output_raster, method='median', size=9, overwrite=True, env=env)


###################### UNUSED ##############################
#def calibrate(scanned_elev, calib_elev, new, env):
#    expression = "{new} = {scanned_elev} - {calib_elev}".format(new=new, calib_elev=calib_elev, scanned_elev=scanned_elev)
#    gcore.run_command('r.mapcalc', expression=expression, overwrite=True, env=env)

#def adjust_scanned_elev(real_elev, scanned_elev, new):
#    res = gcore.read_command('r.regression.line', map1=scanned_elev,
#    map2=real_elev, flags='g')
#    res = gcore.parse_key_val(res, val_type=float)
#
#    expression = "{new} = {a} + {b} * {elev}".format(new=new, a=res['a'], b=res['b'], elev=scanned_elev)
#    grast.mapcalc(expression, overwrite=True)
#    gcore.run_command('r.colors', map=new, color='elevation')
