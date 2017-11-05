# -*- coding: utf-8 -*-
import os

import geopandas as gpd
import numpy as np
import pandas as pd

from bokeh import io, plotting, models, embed
from datetime import timedelta
from glob import glob
from gpxpy import parse, gpxfield
from multiprocessing.pool import ThreadPool
from shapely.geometry import LineString
from sklearn import neighbors, cluster

from stravastats.utils import progbar, haversine, elev_gain_loss


# modify one of gpxpy's parser functions to read extended data
def patched_extensions_parser(self, parser, node, version):
    result = {}

    if node is None:
        return result

    extensions_node = parser.get_first_child(node, self.tag)

    if extensions_node is None:
        return result

    children = parser.get_children(extensions_node)
    if children is None:
        return result

    for child in children:
        extension_attribs = parser.get_children(child)
        for a in extension_attribs:
            result[parser.get_node_name(a)] = parser.get_node_data(a)

    return result


gpxfield.GPXExtensionsField.from_xml = patched_extensions_parser


class StravaData:
    """
    The set of files generated from a Strava data dump.

    Assumes naming conventions has not been changed by the user.
    """
    def __init__(self, folder):
        """
        :param str folder: path to the folder containing the Strava gpx dump
        """
        self.folder = folder
        self.fls = glob('{}/*.gpx'.format(self.folder))
        self.file_count = len(self.fls)
        self.activity_types = list(set([f.split('-')[-1].split('.')[0] for f in self.fls]))
        dates = [pd.to_datetime(' '.join(f.split('/')[-1].split('-')[0:2])) for f in self.fls]
        self.date_range = [min(dates), max(dates)]
        self.data = None
        self.routes = None

    def _choose_files(self, types=None, ranges=None):
        """
        Filter the existing files by activity type(s) or date range(s)

        :param list types: types of activities to consider
        :param list ranges: start datetime ranges of activities to consider. Ranges expected as tuples of strings,
                            with times assumed to be in UTC
        :return: filtered list of files
        :rtype: list
        """
        fls = self.fls
        if types is not None:
            if type(types) != list:
                raise TypeError('"Types" must be a list')
            fls = [f for f in fls if any('-{}'.format(t.lower()) in f.lower() for t in types)]
        if ranges is not None:
            if type(ranges) != list:
                raise TypeError('"Ranges" must be a list')
            ranges = [[pd.to_datetime(dt) for dt in r] for r in ranges]
            fls = [f for f in fls if
                   any(r[0] <= pd.to_datetime(' '.join(f.split('/')[-1].split('-')[:2])) <= r[1] for r in ranges)]
        return fls


class PointData(StravaData):
    """
    Strava data files as the individual recorded points across activities.
    Represents the most 'resolved' level pf data available.
    """
    @staticmethod
    def _get_points(path):
        """
        Extract and format the individual points and associated attributes from the specified file.

        :param str path: path to the gpx file
        :return: parsed points and associated attributes
        :rtype: pd.DataFrame
        """
        with open(path, 'r') as gpx_fle:
            gpx = parse(gpx_fle)
        data_store = []
        for track in gpx.tracks:
            activity_info = {'name': gpx.tracks[0].name, 'file': path.split('/')[-1].split('.')[0]}
            for segment in track.segments:
                for point in segment.points:
                    point_data = {k: v for k, v in point.__dict__.items() if v is not None and k != 'extensions'}
                    point_data.update(point.extensions)
                    point_data.update(activity_info)
                    data_store.append(point_data)
        return pd.DataFrame(data_store)

    def get_data(self, types=None, ranges=None):
        """
        Extract point data from the Strava data dump.

        NOTE: This can take a long time and data is stored in memory.

        :param list types: types of activities to consider.
        :param list ranges: start datetime ranges of activities to consider. Ranges expected as tuples of strings,
                            with times assumed to be in UTC.
        :return: Strava file dump (or filtered subset) parsed into points, as well as parameters used to filter
        :rtype: dict
        """

        fls = self._choose_files(types, ranges)

        print('Parsing {} files...'.format(len(fls)))

        t_pool = ThreadPool()
        result = t_pool.map_async(self._get_points, fls)
        while not result.ready():
            total = int(round(float(len(fls)) / result._chunksize))
            done = total - result._number_left
            progbar(total, done)
        parsed_points = result.get()
        t_pool.close()
        t_pool.join()

        point_data = pd.concat(parsed_points)
        self.data = {'types': types, 'ranges': ranges, 'data': point_data}

        return self.data


class RouteData(StravaData):
    @staticmethod
    def _get_route(path):
        """
        Extract, format, and calculate metrics for the route available in the specified file.

        :param str path: path to the gpx file
        :return: parsed route and associated attributes
        :rtype: dict
        """
        with open(path, 'r') as gpx_fle:
            gpx = parse(gpx_fle)

        data = []
        for track in gpx.tracks:
            activity_info = {'name': gpx.tracks[0].name, 'file': path.split('/')[-1].split('.')[0]}
            for segment in track.segments:
                for point in segment.points:
                    point_data = {k: v for k, v in point.__dict__.items() if v is not None and k != 'extensions'}
                    point_data.update(point.extensions)
                    point_data.update(activity_info)
                    data.append(point_data)
        data_df = pd.DataFrame(data)
        if not data_df.empty:
            data_df.set_index('time', inplace=True)
            name = data_df['name'][0]
            pts = zip(data_df['longitude'], data_df['latitude'])
            route = LineString(pts)
            duration = data_df.index[-1] - data_df.index[0]
            distance = sum([haversine(pair[0], pair[1]) for pair in zip(pts[:-1], pts[1:])])  # in km
            e_gain, e_loss = elev_gain_loss(data_df['elevation'])  # in m
            avg_spd = distance / (duration.total_seconds() / timedelta(hours=1).total_seconds())  # in kph

            return {'file': path.split('/')[-1].split('.')[0], 'name': name, 'geometry': route, 'duration': duration,
                    'distance': distance, 'e_gain': e_gain, 'avg_spd': avg_spd}

    def get_routes(self, types=None, ranges=None):
        """
        Extract route data from the Strava data dump.

        NOTE: This can take a long time and routes are stored in memory.

        :param list types: types of activities to consider.
        :param list ranges: start datetime ranges of activities to consider. Ranges expected as tuples of strings,
                            with times assumed to be in UTC.
        :return: Strava file dump (or filtered subset) parsed into routes, as well as parameters used to filter
        :rtype: dict
        """

        fls = self._choose_files(types, ranges)

        print('Parsing {} files...'.format(len(fls)))

        t_pool = ThreadPool()
        result = t_pool.map_async(self._get_route, fls)
        while not result.ready():
            total = int(round(float(len(fls)) / result._chunksize))
            done = total - result._number_left
            progbar(total, done)
        routes = [r for r in result.get() if r is not None]
        t_pool.close()
        t_pool.join()

        self.routes = {'types': types, 'ranges': ranges,
                       'data': gpd.GeoDataFrame(routes, geometry='geometry', crs={'init': 'epsg:4326'})}

        return self.routes

    def route_stats(self, types=None, ranges=None, force_parse=False):
        """
        Calculate a variety of statistics/metrics from the parsed routes.

        Will parse routes if 1) RouteData.get_routes has not yet been run, or 2) force_parse is set to True

        :param list types: types of activities to consider.
        :param list ranges: start datetime ranges of activities to consider. Ranges expected as tuples of strings,
                            with times assumed to be in UTC.
        :param bool force_parse: force a re-parsing of routes. Otherwise, stats will be generated from the previously
                                 run 'get_routes'
        :return: various statistics/metrics from specified routes
        :rtype: dict
        """
        # TODO Add by_type/by_range
        if not self.routes or force_parse:
            print('Routes not yet parsed.')
            self.get_routes(types, ranges)

        routes = self.routes['data']

        total_dist = routes['distance'].sum()
        fun_dist = self._fun_dist(total_dist)

        total_time = routes['duration'].sum()
        fun_time = self._fun_time(total_time.total_seconds() / timedelta(hours=1).total_seconds())

        total_elev = routes['e_gain'].sum()
        fun_elev = self._fun_elev(total_elev)

        longest_activ = routes.iloc[routes['distance'].idxmax()].to_dict()
        most_elev = routes.iloc[routes['e_gain'].idxmax()].to_dict()

        averages = routes.mean().to_dict()

        return {'total_dist': total_dist, 'total_time': total_time, 'total_elev': total_elev, 'fun_dist': fun_dist,
                'fun_time': fun_time, 'fun_elev': fun_elev, 'longest_activ': longest_activ, 'most_elev': most_elev,
                'average': averages}

    @staticmethod
    def _fun_dist(distance_km):
        """
        Generate a message to put the input distance in context.

        :param float distance_km: distance, in km
        :return: contextualized distance message
        :rtype: str
        """
        if distance_km <= 2e3:
            leo_dist = 2e3
            return "{}% of the way to leaving Low Earth Orbit!".format('%.1f' % ((distance_km / leo_dist) * 100))
        elif distance_km <= 9e3:
            us_dist = 4509.
            return "{}% of the way across the US!".format('%.1f' % ((distance_km / us_dist) * 100))
        elif distance_km <= 40075:
            earth_circ = 40075.
            return "{}% of the way around the Earth!".format('%.1f' % ((distance_km / earth_circ) * 100))
        else:
            moon_dist = 384400.
            return "{}% of the way to the moon!".format('%.1f' % ((distance_km / moon_dist) * 100))

    @staticmethod
    def _fun_time(time_hrs):
        """
        Generate a message to put the input time in context.

        :param float time_hrs: time, in hrs
        :return: contextualized time message
        :rtype: str
        """
        if time_hrs <= 74.:
            hula_t = 74.
            return "{}% as long as the longest hula hooping marathon!".format('%.1f' % ((time_hrs / hula_t) * 100))
        elif time_hrs <= 264.4:
            awake_t = 264.4
            return "{}% as long as the longest someone has stayed awake!".format('%.1f' % ((time_hrs / awake_t) * 100))
        elif time_hrs <= 992.27:
            expert_t = 992.27
            return ("{}% as long as it took to finish the world's longest running race! (4,989 km Self-Transcendence "
                    "Race)").format('%.1f' % ((time_hrs / expert_t) * 100))
        elif time_hrs <= 5e3:
            suit_time = 5e3
            return "{}% as long as it took to fabricate a NASA spacesuit!".format(
                '%.1f' % ((time_hrs / suit_time) * 100))
        else:
            expert_t = 1e4
            return ("{}% of the way to becoming an expert! (according to Malcom Gladwell, "
                    "at least)").format('%.1f' % ((time_hrs / expert_t) * 100))

    @staticmethod
    def _fun_elev(elev_m):
        """
        Generate a message to put the input elevation in context.

        :param float elev_m: elevation, in m
        :return: contextualized elevation message
        :rtype: str
        """
        if elev_m <= 8848.:
            height_everest = 8848.
            return "{}% of the way up Everest!".format('%.1f' % ((elev_m / height_everest) * 100))
        if elev_m <= 35392.:
            height_everest = 8848.
            return "{} times up Everest!".format('%.1f' % (elev_m / height_everest))
        elif elev_m <= 1e5:
            space_h = 1e5
            return "{}% of the way to space!".format('%.1f' % ((elev_m / space_h) * 100))
        else:
            leo_h = 1.8e5
            return "{}% of the way to Low Earth Orbit!".format('%.1f' % ((elev_m / leo_h) * 100))

    def favorite_launches(self, n=3):
        """
        Determine the users 'favorite' launch locations for their activities.

        Defined by clustering start locations and finding the most populated clusters.

        :param int n: number of favorites to return. Note: maximum, may be less.
        :return: coordinates of up to n favorite launch locations
        :rtype: list
        """
        # Endpoints of routes
        endpoints = [[r.coords[0], r.coords[-1]] for r in self.routes['data']['geometry']]
        # Grab both endpoints if start/end in the same(-ish) place, otherwise just grab first point
        starts = np.array([i for sl in [p if haversine(*p) < 0.25 else p[:1] for p in endpoints] for i in sl])
        # points to radians (and switch order to lat/lon)
        starts_r = starts[:, [1, 0]] * (np.pi / 180.)
        # Matrix of distances between points (converted to km)
        dists = neighbors.DistanceMetric.get_metric('haversine').pairwise(starts_r) * 6371

        db = cluster.DBSCAN(eps=.1, min_samples=2, metric='precomputed', n_jobs=-1).fit_predict(dists)

        # 3 clusters with most points
        label, counts = np.unique(db[db != -1], return_counts=True)
        label_top = counts.argsort()[::-1][:n]

        # centroid of each
        centroids = []
        for l in label_top:
            tmp_arr = starts[db == l, :]
            length = tmp_arr.shape[0]
            sum_x = np.sum(tmp_arr[:, 0])
            sum_y = np.sum(tmp_arr[:, 1])
            centroids.append([sum_x / length, sum_y / length])

        return centroids

    def plot_heatmap(self, save_loc='.', return_html_str=False, test=False):
        """
        Generate a personalized heatmap of routes.

        :param str save_loc: path to save location for generated html file, filename of 'route_heatmap'. Default: '.'
        :param bool return_html_str: if True, return the html string needed to embed the generated figure.
                                     Default: False
        :param bool test: flag used during testing, shouldn't be changed.
        :return: html file of map (if save_loc spefified) and/or html string (if return_html_str set to True)
        :rtype: None or str
        """
        try:
            mapbox_key = os.environ['MAPBOX_KEY']
            tiles = models.tiles.WMTSTileSource(url=('https://api.mapbox.com/styles/v1/tdlangland/cj9dewzvu63v72rs3fe1'
                                                     'ioiwx/tiles/256/{{z}}/{{x}}/{{y}}@2x?access_token={}'.format(
                mapbox_key)), attribution=("© <a href='https://www.mapbox.com/about/maps/'>Mapbox</a> © <a href="
                                           "'http://www.openstreetmap.org/copyright'>OpenStreetMap</a> <strong>"
                                           "<a href='https://www.mapbox.com/map-feedback/' target='_blank'>"
                                           "Improve this map</a></strong>"))
        except KeyError:
            pass
            # backup tiles

        routes = self.routes['data'].to_crs(epsg=3857)
        route_xs = [list(l.coords.xy[0]) for l in routes['geometry']]
        route_ys = [list(l.coords.xy[1]) for l in routes['geometry']]
        if test:
            return route_xs, route_ys

        fig = plotting.figure(tools='pan, wheel_zoom')
        fig.axis.visible = False
        fig.add_tile(tiles)
        fig.multi_line(route_xs, route_ys, color='#33d6ff', alpha=0.7, line_width=2)
        if save_loc is not None:
            io.output_file("{}/route_heatmap.html")
        if return_html_str:
            return embed.file_html(fig, title='Route Map')
