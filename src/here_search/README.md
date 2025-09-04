`here_search` is not a package but a namespace.
This directory must not contain a `__init__.py` file.

It sometimes happens that ide are adding an __init__.py file after a namespace directory.
It is producing an error similar to the following when using the package:

```
ImportError: cannot import name 'xxx' from 'here_search' (..../src/here_search/__init__.py)
```



Reference: https://packaging.python.org/en/latest/guides/packaging-namespace-packages/

