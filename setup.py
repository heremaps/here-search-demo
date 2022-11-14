#!/usr/bin/env python
# Used for ort-scan

from setuptools import setup, find_namespace_packages
from pathlib import Path

project_name = "here-search-demo"
package_path = ("here_search", "demo")
src_root = "src"
here = Path(__file__).parent

namespace = {}
with open(Path(here, src_root, Path(*package_path), "__init__.py")) as init_file:
    exec(init_file.read(), namespace)

with open(Path(here, "README.md"), encoding='utf-8') as f:
    long_description = f.read()

setup(name=project_name,
      version=namespace["__version__"],
      description='HERE Geocoding and Search support widgets',
      long_description=long_description,
      long_description_content_type='text/markdown',
      author='HERE Europe B.V.',
      url='https://here.com',
      license='MIT',
      classifiers=[
          'Intended Audience :: Developers',
          'Programming Language :: Python :: 3.7',
          'Programming Language :: Python :: 3.8',
          'Programming Language :: Python :: 3.9',
          'License :: OSI Approved :: MIT License'
      ],
      packages=find_namespace_packages(where=src_root),
      scripts=[Path(src_root, Path(*package_path), "scripts", "here-search-notebooks").as_posix()],
      package_dir={'': src_root},
      include_package_data=True,
      package_data={f'{".".join(package_path)}.notebooks': ['*.ipynb']},
      python_requires=">=3.8",
      install_requires=[p for p in Path(Path(__file__).parent, 'requirements.txt').open().readlines()
                        if not p.startswith("--")],
      dependency_links=[],
      extras_require={"lab": ["xyzservices==2022.1.1", "ipyleaflet", "jupyterlab", "aiohttp"],
                      "lite": ["xyzservices==2022.1.1", "ipywidgets", "ipyleaflet", "jupyterlab", "jupyterlite"]},
      zip_safe=False)
