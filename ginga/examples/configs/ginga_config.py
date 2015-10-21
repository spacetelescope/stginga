def pre_gui_config(ginga):
    pass


def post_gui_config(ginga):
    from ginga.misc.Bunch import Bunch

    # Prefix for custom plugins
    qtpfx = 'ginga.qtw.plugins'  # Qt

    # Add custom global plugins (example)
    #ginga.add_global_plugin(Bunch(module='MyGlobalPlugin', ws='right'))

    # Add custom local plugins (Qt)
    ginga.add_local_plugin(Bunch(module='BackgroundSub', ws='dialogs',
                                 pfx=qtpfx))
    ginga.add_local_plugin(Bunch(module='DQInspect', ws='dialogs',
                                 pfx=qtpfx))

    # Auto start local plugin (example)
    #ginga.add_channel('Image')
    #try:
    #    ginga.start_local_plugin('Image', 'MultiDim', None)
    #except Exception:
    #    pass
