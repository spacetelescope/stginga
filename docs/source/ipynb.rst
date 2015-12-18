.. _stginga-ipynb:

Running stginga with IPython Notebook
=====================================

:mod:`stginga` includes the :mod:`~stginga.nbinteract`, a module to simplify the use of
the ginga viewer inside, or in close association with,
`Jupyter (formerly IPython) notebooks <https://jupyter.org/>`_. The module is
primarily intended to provide a convenience interface to the HTML canvas
backend for ginga in a way that allows interactivity between the viewer and
the python session running in a notebook.

The current functionality in :mod:`~stginga.nbinteract` is focused around setting
up a viewer context and loading data into it.  To see a usage example
demonstrating the current functionality, see :doc:`/notebooks/ginga_nbinteract`. Future
improvements are planned to add more convenience features like accessing ginga
regions or marking up images with only a few lines of code.
