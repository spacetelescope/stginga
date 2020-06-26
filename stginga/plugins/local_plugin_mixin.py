"""Mixin classes for local plugins for Ginga."""

# STDLIB
import json
import os

# THIRD-PARTY
from astropy.utils.misc import JsonCustomEncoder

# GINGA
from ginga.gw import Widgets
from ginga.misc.Future import Future

# Need this for RTD to build successfully without Qt
try:
    from ginga.gw.GwHelp import FileSelection
except ImportError:
    pass

# STGINGA
from stginga import utils

__all__ = ['HelpMixin', 'MEFMixin', 'ParamMixin']


class HelpMixin(object):
    def help(self):
        """Display online help for the plugin."""
        if not self.fv.gpmon.has_plugin('WBrowser'):
            self._help_docstring()
            return

        self.fv.start_global_plugin('WBrowser')

        # need to let GUI finish processing, it seems
        self.fv.update_pending()

        obj = self.fv.gpmon.get_plugin('WBrowser')

        # Unlike Ginga, we do not attempt to download offline doc
        # but just point to online doc directly.
        obj.browse(self.help_url)


class MEFMixin(object):
    """Mixin class for Ginga local plugin that enables manipulation of
    multi-extension FITS images.

    """
    def general_mef_settings(self, prefs):
        """Load MEF settings.

        Sets the following internal variables from Ginga's
        general user preferences::

            self._sci_extname
            self._err_extname
            self._dq_extname
            self._ext_key
            self._extver_key
            self._ins_key
            self._tel_key

        Also sets the following::

            self._no_keyword

        Parameters
        ----------
        prefs : ``ginga.misc.Settings.Preferences``
            Ginga preferences from ``self.fv.get_preferences()``.

        """
        self._no_keyword = 'N/A'

        gen_settings = prefs.create_category('general')
        gen_settings.load(onError='silent')
        self._sci_extname = gen_settings.get('sciextname', 'SCI')
        self._err_extname = gen_settings.get('errextname', 'ERR')
        self._dq_extname = gen_settings.get('dqextname', 'DQ')
        self._ext_key = gen_settings.get('extnamekey', 'EXTNAME')
        self._extver_key = gen_settings.get('extverkey', 'EXTVER')
        self._tel_key = gen_settings.get('telescopekey', 'TELESCOP')
        self._ins_key = gen_settings.get('instrumentkey', 'INSTRUME')

    def _info_for_other_ext(self, image, header):
        """Extract relevant metadata for loading another extension."""
        imfile = image.metadata['path']
        imname = image.metadata['name'].split('[')[0]
        telescope = header.get(self._tel_key, None)
        instrument = header.get(self._ins_key, None)
        extver = header.get(self._extver_key, 0)

        return imfile, imname, telescope, instrument, extver

    def load_err(self, image, header):
        """Find and load ERR extension.

        .. note::

            WFPC2 does not have ERR.

        Parameters
        ----------
        image : ``ginga.AstroImage.AstroImage``
            Ginga image object.

        header : dict
            Header associated with the image.

        Returns
        -------
        errsrc : ``ginga.AstroImage.AstroImage`` or `False`
            ERR image associated with given image, if available.

        """
        imfile, imname, telescope, instrument, extver = self._info_for_other_ext(image, header)  # noqa

        if telescope == 'HST' and instrument == 'WFPC2':
            return False

        err_extnum = (self._err_extname, extver)
        errname = '{0}[{1},{2}]'.format(imname, self._err_extname, extver)
        errsrc = utils.find_ext(imfile, err_extnum)

        # Load ERR image
        if errsrc:
            errsrc = self.autoload_ginga_image(imfile, err_extnum, errname)
        else:
            self.logger.warn('{0} extension not found for '
                             '{1}'.format(err_extnum, imfile))

        return errsrc

    def load_dq(self, image, header):
        """Find and load DQ extension.

        **Special Handling for WFPC2**

        The DQ file has ``c1m`` in its name.
        However, extension name could be either ``'DQ'`` or ``'SCI'``.

        Parameters
        ----------
        image : ``ginga.AstroImage.AstroImage``
            Ginga image object.

        header : dict
            Header associated with the image.

        Returns
        -------
        dqsrc : ``ginga.AstroImage.AstroImage`` or `False`
            DQ image associated with given image, if available.

        """
        imfile, imname, telescope, instrument, extver = self._info_for_other_ext(image, header)  # noqa
        dq_extnum = (self._dq_extname, extver)

        if telescope != 'HST' or instrument != 'WFPC2':
            dqname = '{0}[{1},{2}]'.format(imname, self._dq_extname, extver)
            dqsrc = utils.find_ext(imfile, dq_extnum)

        # Special handling for WFPC2, lots of assumptions
        else:
            imfile = imfile.replace('c0m', 'c1m')
            imname = imname.replace('c0m', 'c1m')
            dqsrc = utils.find_ext(imfile, dq_extnum)

            if not dqsrc:
                dq_extnum = (self._sci_extname, extver)
                dqsrc = utils.find_ext(imfile, dq_extnum)

            dqname = '{0}[{1},{2}]'.format(imname, dq_extnum[0], extver)

        # Load DQ image
        if dqsrc:
            dqsrc = self.autoload_ginga_image(imfile, dq_extnum, dqname)
        else:
            self.logger.error('{0} extension not found for '
                              '{1}'.format(dq_extnum, imfile))

        return dqsrc

    def autoload_ginga_image(self, filename, extnum, cachekey):
        """Automatically load a given image extension into Ginga viewer.

        Parameters
        ----------
        filename : str
            Image filename.

        extnum : int
            Image extension number.

        cachekey : str
            Key for Ginga data cache. Usually, this is in the format of
            ``prefix[extname, extver]``.

        Returns
        -------
        image : ``ginga.AstroImage.AstroImage``
            Ginga image object.

        """
        # Image already loaded
        if cachekey in self.chinfo.datasrc:
            self.logger.debug('Loading {0} from cache'.format(cachekey))
            image = self.chinfo.datasrc[cachekey]

        # Auto load image data
        else:
            self.logger.debug(
                'Loading {0} from {1}'.format(cachekey, filename))
            image = self.fv.load_image(filename, idx=extnum)
            future = Future()
            future.freeze(self.fv.load_image, filename, idx=extnum)
            image.set(path=filename, idx=extnum, name=cachekey,
                      image_future=future)
            self.fv.add_image(cachekey, image, chname=self.chname, silent=True)
            self.fv.advertise_image(self.chname, image)

        return image


class ParamMixin(object):
    """Mixin class for Ginga local plugin that enables the feature to
    save/load parameters.

    """
    def build_param_gui(self, container):
        """Call this in ``build_gui()`` to create 'Load Param' and 'Save Param'
        buttons.

        Parameters
        ----------
        container : widget
            The widget to contain these buttons.

        """
        captions = (('Load Param', 'button', 'Save Param', 'button'), )
        w, b = Widgets.build_info(captions, orientation=self.orientation)
        self.w.update(b)

        b.load_param.set_tooltip('Load previously saved parameters')
        b.load_param.add_callback(
            'activated', lambda w: self.load_params_cb())

        b.save_param.set_tooltip('Save {0} parameters'.format(str(self)))
        b.save_param.add_callback(
            'activated', lambda w: self.save_params())

        container.add_widget(w, stretch=0)

        # Initialize file save dialog
        self.filesel = FileSelection(self.fv.w.root.get_widget())

    def params_dict(self):
        """Return current parameters as a dictionary."""
        raise NotImplementedError('To be implemented by Ginga local plugin')

    def save_params(self):
        """Save parameters to a JSON file."""
        pardict = self.params_dict()
        fname = Widgets.SaveDialog(
            title='Save parameters', selectedfilter='*.json').get_path()
        if fname is None:  # Cancel
            return
        if os.path.exists(fname):
            self.logger.warn('{0} will be overwritten'.format(fname))
        with open(fname, 'w') as fout:
            json.dump(pardict, fout, indent=4, sort_keys=True,
                      cls=JsonCustomEncoder)
        self.logger.info('Parameters saved as {0}'.format(fname))

    def load_params_cb(self):
        """Allow user to select JSON file to load."""
        self.filesel.popup('Load JSON file', self.load_params, initialdir='.',
                           filename='JSON files (*.json)')

    def load_params(self, filename):
        """Load previously saved parameters from a JSON file."""
        if not os.path.isfile(filename):
            return True

        with open(filename) as fin:
            self.logger.info('{0} parameters loaded from {1}'.format(
                str(self), filename))
            pardict = json.load(fin)

        self.ingest_params(pardict)

    def ingest_params(self, pardict):
        """Ingest dictionary containing plugin parameters into plugin
        GUI and internal variables."""
        raise NotImplementedError('To be implemented by Ginga local plugin')
