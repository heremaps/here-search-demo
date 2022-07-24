from setuptools import setup, find_packages
from here_search import __version__

setup(name='here-search-demo',
      version=__version__,
      description='HERE Geocoding and Search support widgets',
      packages=find_packages(),
      package_data = {'*' :['LICENSE', '*.ipynb']},
      scripts=['./here-search-notebook'],
      entry_points={'console_scripts': ['here-search-console=here_search.terminal.simple_app:cli']},
      python_requires='>=3.6',
      zip_safe=False)
