from setuptools import setup
from search import __version__

setup(name='here-search-notebook',
      version=__version__,
      description='HERE Geocoding and Search support widgets',
      packages=['search'],
      data_files=[('.', ['demo.ipynb'])],
      scripts=['./here-search-notebook'],
      python_requires='>=3.6',
      zip_safe=False)
