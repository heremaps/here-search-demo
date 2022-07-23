## Contributing

    $ pip install twine wheel
    $ python setup.py sdist bdist_wheel
    $ twine upload --skip-existing --repository-url https://artifactory.in.here.com/artifactory/api/pypi/onesearch-pypi dist/*