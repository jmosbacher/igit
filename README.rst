====
iGit
====

Git-like interval versioning.

.. image:: https://img.shields.io/pypi/v/igit.svg
        :target: https://pypi.python.org/pypi/igit

.. image:: https://img.shields.io/travis/jmosbacher/igit.svg
        :target: https://travis-ci.com/jmosbacher/igit

.. image:: https://readthedocs.org/projects/igit/badge/?version=latest
        :target: https://igit.readthedocs.io/en/latest/?badge=latest
        :alt: Documentation Status


Git-like version control for data that is organized in a interval tree.
Analogies to git:
git <--> igit
blob <--> blob
filename <--> interval
tree/folder <--> interval tree

in iGit the basic structure being versioned is a hiearchy of intervals instead of a hierchy of files.
An interval can contain data (analog of a file) or a tree of other intervals (analog of a folder).
This kind of structure is useful e.g. when tracking arrays of data or 
configuration parameters that have defined intervals of validity attached to them.


* Free software: MIT
* Documentation: https://igit.readthedocs.io.


Features
--------

* TODO

Credits
-------
This package relies heavily on the intervaltree package for all interval tree manipulation

This package was created with Cookiecutter_ and the `briggySmalls/cookiecutter-pypackage`_ project template.

.. _Cookiecutter: https://github.com/audreyr/cookiecutter
.. _`briggySmalls/cookiecutter-pypackage`: https://github.com/briggySmalls/cookiecutter-pypackage
