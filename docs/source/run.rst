.. _stginga-run:

Running Ginga With stginga Plugins
==================================

``stginga`` includes additional plugins to beyond those provided by Ginga
itself that add functionality.  There are a few different ways to start
Ginga in a way that will make it recognize those plugins; Only use *one* of the
following options:

#. :ref:`stginga-run-script`
#. :ref:`stginga-run-gingaconfig`
#. :ref:`stginga-run-manual`


.. _stginga-run-script:

The stginga Script
------------------

The simplest way is to simply use a script packaged with ``stginga`` that knows
how to preload the :ref:`STScI plugins <stginga-plugins>`::

    stginga [args]

The accepted command line arguments are the same as for standard Ginga, except
that there is no need to use ``--plugins`` and ``--modules`` to load
STScI plugins.


.. _stginga-run-gingaconfig:

Change Ginga Configuration to Always Load stginga
-------------------------------------------------

If you wish to have the ``stginga`` plugins *always* loaded when you
start Ginga, you can set your local configuration to do this automatically.
The key is to use Ginga's built-in configuration machinery.

Create a ``$HOME/.ginga/ginga_config.py`` file or modify your existing copy
with the following contents::

    def pre_gui_config(ginga):
        from stginga import load_plugins
        load_plugins(ginga)

    def post_gui_config(ginga):
        ginga.start_global_plugin('ChangeHistory')

Then, you can run Ginga natively as follows::

    ginga [args]


.. _stginga-run-manual:

Manually Load stginga Plugins
-----------------------------

You can also run Ginga natively and just specify the plugins you want directly::

    ginga --plugins=stginga.plugins.BackgroundSub,stginga.plugins.BadPixCorr,stginga.plugins.DQInspect,stginga.plugins.MIPick,stginga.plugins.SNRCalc --modules=stginga.plugins.MultiImage [args]

If you do it this way, you need to manually start ``ChangeHistory`` global
plugin from Ginga viewer, as it is not started by default in Ginga.
