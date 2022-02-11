

Building

    python3 setup.py clean --all sdist bdist_wheel

Publishing

    python3 -m twine upload --repository here-search-notebook dist/*

Tagging

    version=v$(python -c "import search; print(search.__version__)")_int && git tag -a $version -m "$version"
    git push origin $version