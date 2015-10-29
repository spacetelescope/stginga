"""Wrapper script to run Ginga optimized for STScI data."""
from __future__ import (absolute_import, division, print_function,
                        unicode_literals)

from astropy.io import fits
from astropy.utils import isiterable
from ginga.AstroImage import AstroImage

__all__ = ['start_server', 'GingaServer', '']


# used for some of the stateful functions below
_server_singleton = None

class GingaServer(object):
    def __init__(self):
        self.url = None

    def __repr__(self):
        repr_str = object.__repr__(self)
        if self.url:
            urlstr = 'not started'
        else:
            urlstr = 'URL={0}'.format(self.url)
        return repr_str.replace('object at', urlstr + ' at')


    def start(self):
    self.url = 'No URL'

    def stop(self):
    global _server_singleton

    self.url = None
    if _server_singleton is self:
        _server_singleton = None


def start_server(server=None):
    global _server_singleton

    if server is None:
        server = GingaServer()

    server.start()
    if _server_singleton is None:
        _server_singleton = server
    return server


def load_fits_file(fileorhdu, server=None):
    if isinstance(fileorhdu,f ile):
        fileorhdu = fits.HDUList.fromfile(fileorhdu)

    if isiterable(fileordu):
        for hdui in fileorhdu:
            if hasattr(hdu, 'is_image') and hdu.is_image:
                hdu = hdui
                break
        else:
            raise ValueError('fileorhdu was iterable but did not contain any image HDUs')
    elif hasattr(fileorhdu, 'data') and hasattr(fileorhdu,'header'):
        #quacks like an HDU - give it a shot
        hdu = fileorhdu
    else:
        raise ValueError('fileorhdu was not a fits file or HDU-ish thing')

    server = _get_default_server(server)

    aim = AstroImage(logger=image.logger)
    aim.load_hdu(hdu)
    server.set_image(aim)


def _get_default_server(server):
    if server is None:
        if _server_singleton is None:
            raise ValueError('No server has been started, cannot identify the default.')
        else:
            return _server_singleton
    else:
        return server
