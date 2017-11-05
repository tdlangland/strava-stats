from setuptools import setup, find_packages
from codecs import open
from os import path

here = path.abspath(path.dirname(__file__))

# Get the long description from the README file
with open(path.join(here, 'README.md'), encoding='utf-8') as f:
    long_description = f.read()

with open(path.join(here, 'requirements.txt')) as f:
    install_requires = f.read()

setup(
    name='strava-stats',
    version='0.0.1',
    description='A quick project to parse, summarize, and visualize bulk downloads from Strava',
    long_description=long_description,
    url='https://github.com/tdlangland/strava-stats',
    author='Todd Langland',
    author_email='tlangland@comcast.net',
    license='MIT',
    packages=find_packages(exclude=['data', 'dist', 'docs']),
    install_requires=install_requires,
    include_package_data=True,
)
