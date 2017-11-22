"""Wrapper script to run Ginga optimized for STScI data."""
from __future__ import absolute_import, division, print_function

import os

from astropy.io import fits
from astropy.utils import isiterable
from astropy.utils.decorators import deprecated

import tornado.httpserver
import tornado.web
import tornado.ioloop

from ginga.misc import log, Task
from ginga.AstroImage import AstroImage
from ginga.web.pgw import Widgets, js, PgHelp, ipg

__all__ = ['GingaServer']


@deprecated('0.2.2', alternative="See Ginga's example notebook")
class GingaServer(object):
    """IPython Notebook server for ``stginga``.

    Parameters
    ----------
    host : str
        Host name or IP address.

    port : int
        Port number.

    logger
        Python logger. This uses ``nbinteract_server`` logger by default.

    numthreads : int
        Number of multiprocessing threads to use.

    Attributes
    ----------
    host, port, logger
        Same as inputs

    thread_pool
        Thread pool for the given number of threads.

    tornado_app
        Tornado web application.

    app
        Ginga widget application.

    viewers : dict
        Maps viewer name to Ginga image viewer.

    """
    def __init__(self, host='localhost', port=9909, logger=None, numthreads=5):
        self.tornado_app = None
        self.viewers = {}
        self.host = host
        self.port = port

        if logger is None:
            logger = log.get_logger("nbinteract_server", null=True)
        self.logger = logger

        self.thread_pool = Task.ThreadPool(numthreads, logger)
        self.app = Widgets.Application(logger=self.logger,
                                       base_url=self.base_url)

    @property
    def base_url(self):
        """Base URL for this server."""
        return "http://{0}:{1}/app".format(self.host, self.port)

    def __repr__(self):
        repr_str = object.__repr__(self)
        if self.url:
            urlstr = 'not started'
        else:
            urlstr = 'URL={0}'.format(self.url)
        return repr_str.replace('object at', urlstr + ' at')

    def start(self, create_main_window=True):
        """Start server.

        Parameters
        ----------
        create_main_window : bool
            Create new Ginga image viewer.

        """
        self.thread_pool.startall()

        # TODO: DONT DO THIS. Use package data instead
        js_path = os.path.dirname(js.__file__)

        self.tornado_app = tornado.web.Application([
            (r"/js/(.*\.js)", tornado.web.StaticFileHandler,
             {"path":  js_path}),
            (r"/app", PgHelp.WindowHandler,
             dict(name='Application', url='/app', app=self.app)),
            (r"/app/socket", PgHelp.ApplicationHandler,
             dict(name='Ginga', app=self.app)),
            ], logger=self.logger)

        self.tornado_server = tornado.httpserver.HTTPServer(self.tornado_app)
        self.tornado_server.listen(self.port, self.host)

        if create_main_window:
            self.new_viewer('Main Viewer')

    def stop(self):
        """Stop server (**NOT IMPLEMENTED**)."""
        raise NotImplementedError

    def new_viewer(self, viewer_name):
        """Create a new viewer with the given name.

        Parameters
        ----------
        viewer_name : str
            Name of the new Ginga image viewer.

        Returns
        -------
        viewer
            Ginga image viewer.

        Raises
        ------
        ValueError
            Viewer name already exists.

        """
        if viewer_name in self.viewers:
            raise ValueError('Viewer {} already exists'.format(viewer_name))

        # our own viewer object, customized with methods (see above)
        self.viewers[viewer_name] = ipg.ImageViewer(
            self.logger, self.app.make_window(viewer_name))

        return self.viewers[viewer_name]

    def get_viewer_urls(self):
        """Get viewer URLs.

        Returns
        -------
        urls : dict
            Maps viewer name to corresponding URL.

        """
        return {name: viewer.top.url for name, viewer in self.viewers.items()}

    def load_fits(self, fileorhdu, viewer_name='Main Viewer'):
        """Load FITS image into the desired Ginga image viewer.

        Parameters
        ----------
        fileorhdu
            File or HDU list object.

        viewer_name : str
            Name of Ginga image viewer to display to.

        Raises
        ------
        KeyError
            Viewer name does not exist.

        ValueError
            Invalid file or HDU list object, or HDU list does not contain any
            image.

        """
        if isinstance(fileorhdu, file):
            fileorhdu = fits.HDUList.fromfile(fileorhdu)

        if isiterable(fileorhdu):
            for hdui in fileorhdu:
                if hasattr(hdui, 'is_image') and hdui.is_image:
                    hdu = hdui
                    break
            else:
                raise ValueError(
                    'fileorhdu was iterable but did not contain any '
                    'image HDUs')
        elif hasattr(fileorhdu, 'data') and hasattr(fileorhdu, 'header'):
            # quacks like an HDU - give it a shot
            hdu = fileorhdu
        else:
            raise ValueError('fileorhdu was not a fits file or HDU-ish thing')

        viewer = self.viewers[viewer_name]
        if viewer.fitsimage.get_image() is None:
            aim = AstroImage(logger=self.logger)
            aim.load_hdu(hdu)
            viewer.fitsimage.set_image(aim)
        else:
            viewer.fitsimage.get_image().load_hdu(hdu)
