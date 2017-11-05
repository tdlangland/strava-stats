# Strava Stats

Quick little project to generate some descriptive statistics,
light analysis, and plots from [bulk downloads](https://support.strava.com/hc/en-us/articles/216918437-Exporting-your-Data-and-Bulk-Export#Bulk)
of Strava files (`.gpx`)

## Getting Started

These instructions will get you a copy of the project up and running on
your local machine for development and testing purposes.

### Installing

I would recommend working with [virtualenv/virtualenvwrapper](http://docs.python-guide.org/en/latest/dev/virtualenvs/#virtualenvwrapper)
to keep dependencies clean.

#### For general usage:

Pip install from Git
```
pip install git+https://github.com/tdlangland/strava-stats.git
```


#### For dev/testing:

Clone from Git
```
git clone https://github.com/tdlangland/strava-stats.git
```

Requirements can be found in [`requirements.txt`](requirements.txt)

### Usage

If you don't yet have your [bulk Strava file export](https://support.strava.com/hc/en-us/articles/216918437-Exporting-your-Data-and-Bulk-Export#Bulk)
, a couple example files can be found in the [`data`](https://github.com/tdlangland/strava-stats/tree/master/data)
directory of this repo.

```
from pprint import pprint
from stravastats import core

# Define the directory containing your exported files
export_dir = './data'

# Get some information about the files in your data dump
data_dump = core.StravaData(export_dir)

print(data_dump.file_count)
print(data_dump.activity_types)
print(data_dump.date_range)


# Get point data from the files (the most granular data)
points = core.PointData(export_dir)

run_points = points.get_data(types=['run'])
may_points = points.get_data(ranges=[('2017-05-01', '2017-06-01'])
# Careful with this next one, if you have a lot of activities this can be VERY LARGE
all_points = points.get_data()


# Points are great and all, but how about the actual routes!
routes = core.RouteData(export_dir)

all_routes = routes.get_routes()

# Maybe some summary statisitics about those routes?
pprint(routes.route_stats())

# What are your favorite places to start activities?
routes.favorite_launches()

# I want a heatmap just for myself!
routes.plot_heatmap()

```

### Running Tests

Assuming you have cloned the repo and obtained the necessary
[requirements](requirements.txt):

From the root of strava-stats:
```
python -m unittest -v test_stravastats.py
```

## License

This project is licensed under the MIT License - see the
[LICENSE.md](LICENSE.md) file for details
