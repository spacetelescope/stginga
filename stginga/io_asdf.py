"""
Module to handle ASDF for JWST.

See also:

* http://jwst-pipeline.readthedocs.io/en/latest/
* https://jwst-docs.stsci.edu/display/JDAT/JWST+File+Names%2C+Formats%2C+and+Data+Structures
* https://confluence.stsci.edu/display/SCSB/JWST+Science+Data+Products
* http://asdf.readthedocs.io/en/latest/

"""

try:
    # Necessary libraries
    import asdf  # noqa
    import gwcs  # noqa
    # Data models for JWST
    from jwst import datamodels
except ImportError:
    have_jwst_asdf = False
else:
    have_jwst_asdf = True

__all__ = ['AsdfInFitsFileHandler']


class ASDFError(Exception):
    pass


class AsdfInFitsFileHandler:
    """Class to handle ASDF-in-FITS format for JWST."""

    def __init__(self, logger):
        if not have_jwst_asdf:
            raise ASDFError(
                'Need asdf, gwcs, and jwst installed to use this file handler')

        self.logger = logger

    def register_type(self, name, klass):
        self.factory_dict[name.lower()] = klass

    def load_file(self, filespec, dstobj=None, **kwargs):
        self.logger.debug("Loading file '{}' ...".format(filespec))
        self.asdf_f = datamodels.open(filespec)

        if len(self.asdf_f.tree) == 0:  # Normal FITS
            self.close()
            raise ASDFError('Not an ASDF-in-FITS format, use FITS handler')

        # Only load image for now
        if dstobj is None:
            obj_class = self.factory_dict.get('image', None)
            if obj_class is None:
                raise ASDFError(
                    "I don't know how to load objects of kind 'image'")

            dstobj = obj_class(logger=self.logger)

        # TODO: have to open and return something.
        # TODO: how to turn data, err, dq into different HDUs for AstroImage and MultiDim -- Wait for James D to implement fitsinfo-like func?
        # TODO: need to understand GWCS (over at Ginga?) and assign asdf_f.meta.wcs to AstroImage.wcs .

    def save_as_file(self, path, data, header, **kwargs):
        raise NotImplementedError(
            'Writing out this format is not yet supported')

    def close(self):
        self.asdf_f.close()
        self.asdf_f = None
