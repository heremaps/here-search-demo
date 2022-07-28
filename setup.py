from setuptools import setup, find_namespace_packages
from pathlib import Path

project_name = "here-search-demo"
package_name = "here_search"
package_path = "src"

namespace = {}
with open(Path(package_path, package_name, "__init__.py")) as init_file:
    exec(init_file.read(), namespace)

setup(name=project_name,
      version=namespace["__version__"],
      description='HERE Geocoding and Search support widgets',
      packages=find_namespace_packages(where=package_path),
      scripts=[Path(package_path, package_name, "scripts", "here-search-notebooks").as_posix()],
      package_dir={'': package_path},
      package_data={f'{package_name}.notebooks': ['*.ipynb']},
      entry_points={'console_scripts': ['here-search-console=here_search.terminal.simple_app:cli']},
      install_requires=[p for p in Path(Path(__file__).parent, 'requirements.txt').open().readlines()
                        if not p.startswith("--")],
      python_requires=">=3.6",
      zip_safe=False)
