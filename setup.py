from setuptools import setup, find_packages
from here_search import __version__

setup(name='here-search',
      version=__version__,
      description='HERE Geocoding and Search support widgets',
      packages=find_packages(),
      data_files=[('docs', ['docs/oneboxmap.ipynb', 'docs/oneboxmap_ext.ipynb'])],
      scripts=['./here-search-notebook', './here-search-console'],
      python_requires='>=3.6',
      zip_safe=False)
