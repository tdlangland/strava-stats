import sys

from math import radians, cos, sin, asin, sqrt


def elev_gain_loss(elev_data, smooth_time=25):
    """
    Calculate elevation gain and loss over the course of the activity.

    Elevation profile smoothed to reduce the impact of short-term elevation noise.

    Gain and loss defined as cumulative sum of positive and negative 1st discrete difference, respectively.

    :param pd.Series elev_data: series of elevation data, indexed with timestamp
    :param int smooth_time: number of seconds to smooth input data before calculating changes
    :return: (elevation gain, elevation loss)
    :rtype: tuple
    """
    # smooth input data by n seconds
    elev_data = elev_data.rolling('{}s'.format(str(smooth_time))).mean()

    # gain and loss calculation
    gain = sum([i for i in elev_data.diff() if i > 0])
    loss = sum([i for i in elev_data.diff() if i < 0])

    return gain, loss


def haversine(pt1, pt2):
    """
    Calculate the great circle distance between two points on the earth (specified in decimal degrees).

    :param array-like pt1: lon, lat of first point
    :param array-like pt2: lon, lat of second point
    :return: great circle distance between points (in km)
    :rtype: float
    """
    lon1, lat1 = pt1
    lon2, lat2, = pt2

    # convert decimal degrees to radians
    lon1, lat1, lon2, lat2 = map(radians, [lon1, lat1, lon2, lat2])

    # haversine formula
    dlon = lon2 - lon1
    dlat = lat2 - lat1
    a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
    c = 2 * asin(sqrt(a))
    r = 6371  # Radius of earth in kilometers. Use 3956 for miles

    return c * r


def progbar(total, progress, flush=True):
    """
    Displays and updates a console progress bar.

    Source: https://stackoverflow.com/a/45868571/3412205

    :param int total: total iterations
    :param int progress: current iteration
    :param bool flush: whether to flush stdout (force write). Default: True
    :return: None
    """
    barlength, status = 20, ""
    progress = float(progress) / float(total)
    if progress >= 1.:
        progress, status = 1, "\r\n"
    block = int(round(barlength * progress))
    text = "\r[{}] {:.0f}% {}".format(
        "#" * block + "-" * (barlength - block), round(progress * 100, 0),
        status)
    sys.stdout.write(text)
    if flush:
        sys.stdout.flush()