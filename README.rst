====
iGit
====

Git-like interval versioning.


**EXPERIMENTAL** Use at your own risk.


.. image:: https://img.shields.io/pypi/v/igit.svg
        :target: https://pypi.python.org/pypi/igit

.. image:: https://img.shields.io/travis/jmosbacher/igit.svg
        :target: https://travis-ci.com/jmosbacher/igit

.. image:: https://readthedocs.org/projects/igit/badge/?version=latest
        :target: https://igit.readthedocs.io/en/latest/?badge=latest
        :alt: Documentation Status


Git-like version control of data that is organized using interval trees as well as the simple string->value trees used in file systems.
Analogies to git:
git <--> igit
blob <--> blob
filename <--> interval
tree/folder <--> interval tree

in iGit the structure being versioned is a hiearchy of trees and blobs like git, only instead of just 
supporting folder-like trees (string->value mapping) iGit supports interval trees as well.
An interval tree maps intervals to data, data can contain a python object (analog of a file) or
another tree (analog of a folder). This kind of structure is useful e.g. when tracking arrays of data or 
configuration parameters that have defined intervals of validity attached to them. In these cases its useful
to be able to associate a unique piece of data with an interval of two integers (e.g. an array index or timestamp)
instead of a string of characters like a filename.


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
