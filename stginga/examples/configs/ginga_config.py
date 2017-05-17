def pre_gui_config(ginga):
    from ginga.util.catalog import AstroPyCatalogServer

    # TODO: Add MAST interface when available on Astroquery.
    # Add Cone Search services
    catalogs = [
        ('The HST Guide Star Catalog, Version 1.2 (Lasker+ 1996) 1',
         'GSC_1.2'),
        ('The PMM USNO-A1.0 Catalogue (Monet 1997) 1', 'USNO_A1'),
        ('The USNO-A2.0 Catalogue (Monet+ 1998) 1', 'USNO_A2'),
    ]
    bank = ginga.get_ServerBank()
    for longname, shortname in catalogs:
        obj = AstroPyCatalogServer(
            ginga.logger, longname, shortname, '', shortname)
        bank.addCatalogServer(obj)


def post_gui_config(ginga):
    pass
