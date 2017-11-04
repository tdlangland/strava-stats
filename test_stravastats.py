import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import unittest

import numpy as np
import pandas as pd

from contextlib import contextmanager
from stravastats import elev_gain_loss, haversine, progbar, StravaData, PointData, RouteData
from StringIO import StringIO


@contextmanager
def captured_output():
    new_out, new_err = StringIO(), StringIO()
    old_out, old_err = sys.stdout, sys.stderr
    try:
        sys.stdout, sys.stderr = new_out, new_err
        yield sys.stdout, sys.stderr
    finally:
        sys.stdout, sys.stderr = old_out, old_err


class TestElev(unittest.TestCase):
    def test_elev(self):
        elevs = pd.Series(np.sin(np.linspace(-np.pi, np.pi, 201)),
                          index=pd.date_range('1970-01-01', periods=201, freq='1S'))
        gain, loss = elev_gain_loss(elevs)
        self.assertAlmostEqual(gain, 1.9490708681467757)
        self.assertAlmostEqual(loss, -1.5903204474031412)


class TestHaver(unittest.TestCase):
    def test_haversine(self):
        p1 = (-122.395933, 37.781006)
        p2 = (-72.289631, 43.701321)
        self.assertAlmostEqual(haversine(p1, p2), 4207.419453963274)


class TestProgbar(unittest.TestCase):
    def test_progbar0(self):
        with captured_output() as (out, err):
            progbar(100, 0)
            output = out.getvalue().strip()
        self.assertEqual(output, '[--------------------] 0%')

    def test_progbar50(self):
        with captured_output() as (out, err):
            progbar(100, 50)
            output = out.getvalue().strip()
        self.assertEqual(output, '[##########----------] 50%')

    def test_progbar100(self):
        with captured_output() as (out, err):
            progbar(100, 100)
            output = out.getvalue().strip()
        self.assertEqual(output, '[####################] 100%')


class TestStavaData(unittest.TestCase):
    def setUp(self):
        self.data = StravaData('./data')

    def test_file_find(self):
        self.assertEqual(self.data.fls, ['./data/20170520-152045-Ride.gpx', './data/20170520-200310-Run.gpx'])

    def test_file_count(self):
        self.assertEqual(self.data.file_count, 2)

    def test_act_types(self):
        self.assertEqual(self.data.activity_types, ['Ride', 'Run'])

    def test_dt_range(self):
        self.assertEqual(self.data.date_range,
                         [pd.to_datetime(d) for d in ['2017-05-20 15:20:45', '2017-05-20 20:03:10']])

    def test_file_choose_nomod(self):
        self.assertEqual(self.data._choose_files(), self.data.fls)

    def test_file_choose_type(self):
        self.assertEqual(self.data._choose_files(types=['ride']), ['./data/20170520-152045-Ride.gpx'])

    def test_file_choose_range(self):
        self.assertEqual(self.data._choose_files(ranges=[('2017-05-20 20:00:00', '2017-05-20 21:00:00')]),
                         ['./data/20170520-200310-Run.gpx'])

    def test_file_choose_both(self):
        self.assertEqual(self.data._choose_files(types=['Ride'],
                                                 ranges=[('2017-05-20 20:00:00', '2017-05-20 21:00:00')]),
                         [])


class TestPointData(unittest.TestCase):
    def setUp(self):
        self.point_data = PointData('./data')

    def test_get_all_data(self):
        data = self.point_data.get_data()
        self.assertEqual(data['ranges'], None)
        self.assertEqual(data['types'], None)
        self.assertEqual(len(data['data']), 4565)

    def test_get_type_data(self):
        data = self.point_data.get_data(types=['run'])
        self.assertEqual(data['ranges'], None)
        self.assertEqual(data['types'], ['run'])
        self.assertEqual(len(data['data']), 466)

    def test_get_range_data(self):
        data = self.point_data.get_data(ranges=[('2017-05-20 20:00:00', '2017-05-20 21:00:00')])
        self.assertEqual(data['ranges'], [('2017-05-20 20:00:00', '2017-05-20 21:00:00')])
        self.assertEqual(data['types'], None)
        self.assertEqual(len(data['data']), 466)


class TestRouteData(unittest.TestCase):
    def setUp(self):
        self.route_data = RouteData('./data')
        self.single_route = self.route_data._get_route(self.route_data.fls[1])
        self.all_routes = self.route_data.get_routes()
        self.stats = self.route_data.route_stats()
        self.launches = self.route_data.favorite_launches()

    def test_route_dist(self):
        self.assertAlmostEqual(self.single_route['distance'], 8.321373349324361)

    def test_route_name(self):
        self.assertEqual(self.single_route['name'], 'Jog out the ride w/ N')

    def test_e_gain(self):
        self.assertAlmostEqual(self.single_route['e_gain'], 25.476825396825674)

    def test_geom(self):
        self.assertEqual(self.single_route['geometry'].coords[0], (-122.535187, 37.898567))
        self.assertEqual(self.single_route['geometry'].coords[-1], (-122.535837, 37.898531))
        self.assertAlmostEqual(self.single_route['geometry'].length, 0.08429623121324899)
        self.assertEqual(self.single_route['geometry'].type, 'LineString')

    def test_avg_spd(self):
        self.assertAlmostEqual(self.single_route['avg_spd'], 9.46207961388746)

    def test_file_name(self):
        self.assertEqual(self.single_route['file'], '20170520-200310-Run')

    def test_route_duration(self):
        self.assertEqual(self.single_route['duration'].total_seconds(), 3166.0)

    def test_all_routes(self):
        self.assertEqual(len(self.all_routes['data']), 2)

    def test_route_stats_dist(self):
        self.assertAlmostEqual(self.stats['total_dist'], 99.45807461332295)

    def test_route_stats_fun_dist(self):
        self.assertEqual(self.stats['fun_dist'], '5.0% of the way to leaving Low Earth Orbit!')

    def test_route_stats_time(self):
        self.assertEqual(self.stats['total_time'].total_seconds(), 19249.0)

    def test_route_stats_fun_time(self):
        self.assertEqual(self.stats['fun_time'], '7.2% as long as the longest hula hooping marathon!')

    def test_route_stats_elev(self):
        self.assertAlmostEqual(self.stats['total_elev'], 1165.6640799070269)

    def test_route_stats_fun_elev(self):
        self.assertEqual(self.stats['fun_elev'], '13.2% of the way up Everest!')

    def test_route_stats_longest(self):
        self.assertEqual(self.stats['longest_activ']['name'], 'Fog to sun')

    def test_route_stats_highest(self):
        self.assertEqual(self.stats['most_elev']['name'], 'Fog to sun')

    def test_route_stats_avgs(self):
        self.assertEqual(self.stats['average']['duration'].total_seconds(), 9624.5)
        self.assertAlmostEqual(self.stats['average']['distance'], 49.729037306661475)
        self.assertAlmostEqual(self.stats['average']['avg_spd'], 14.93100637258431)
        self.assertAlmostEqual(self.stats['average']['e_gain'], 582.83203995351346)

    def test_favorite_launches(self):
        expected = [i for sl in [[-122.535512, 37.898549000000003], [-122.537542, 37.898762500000004]] for i in sl]
        observed = [i for sl in self.launches for i in sl]
        _ = [self.assertAlmostEqual(o, expected[i]) for i, o in enumerate(observed)]

    def test_heatmap_plot(self):
        xs, ys = self.route_data.plot_heatmap(test=True)
        self.assertEqual(len(xs[0]), 4099)
        self.assertAlmostEqual(xs[0][0], -13640819.004889188)
        self.assertEqual(len(ys[0]), 4099)
        self.assertAlmostEqual(ys[0][0], 4565143.444592611)


if __name__ == '__main__':
    unittest.main()
