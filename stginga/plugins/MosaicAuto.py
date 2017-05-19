"""Automatic mosaic local plugin for Ginga."""
from __future__ import absolute_import, division, print_function
from ginga.util.six import itervalues

# STDLIB
import os

# THIRD-PARTY
from astropy.io import ascii
from astropy.wcs import WCS

# GINGA
from ginga.AstroImage import AstroImage
from ginga.gw import Widgets
from ginga.misc import Bunch
from ginga.rv.plugins.Mosaic import Mosaic
from ginga.util.toolbox import generate_cfg_example

# STGINGA
from stginga.plugins.local_plugin_mixin import HelpMixin

__all__ = []


class MosaicAuto(HelpMixin, Mosaic):
    """Mosaic with option to highlight individual component."""
    def __init__(self, fv, fitsimage):
        super(MosaicAuto, self).__init__(fv, fitsimage)

        self.help_url = ('http://stginga.readthedocs.io/en/latest/stginga/'
                         'plugins_manual/mosaicauto.html')

        # To store individual images and their footprints
        self._wcs_origin = 0
        self._imlist = {}
        self.imlist_columns = [('Image', 'IMAGE')]
        self.footprintstag = None

        self.list_plugin_obj = self.fv.gpmon.get_plugin('Contents')

        # CURRENTLY DISABLED. Because having a manual button might make it
        # easier to add "recreate" feature in the future, if needed.
        # This enables auto-mosaic whenever an image is loaded.
        # fv.add_callback('add-image', self.add_image_cb)

        # CURRENTLY DISABLED.
        # This clears result when any image is removed from channel.
        # fv.add_callback('remove-image', lambda *args: self.remove_mosaic())

    def build_gui(self, container):
        """Build GUI such that image list area is maximized."""
        vbox, sw, orientation = Widgets.get_oriented_box(container)

        self.treeview = Widgets.TreeView(auto_expand=True,
                                         sortable=True,
                                         selection='multiple',
                                         use_alt_row_color=True)
        self.treeview.setup_table(self.imlist_columns, 1, 'IMAGE')
        self.treeview.add_callback('selected', self.draw_footprint_cb)
        container.add_widget(self.treeview, stretch=1)

        captions = (('Create Mosaic', 'button', 'Save Selection', 'button',
                     'Spacer1', 'spacer'), )
        w, b = Widgets.build_info(captions, orientation=orientation)
        self.w.update(b)

        # DO NOT REALLY NEED THIS WHEN add-image CALLBACK WORKS AGAIN
        b.create_mosaic.set_tooltip(
            'Build mosaic from currently opened images')
        b.create_mosaic.add_callback('activated', lambda w: self.auto_mosaic())

        b.save_selection.set_tooltip('Save selected image(s) to output XML')
        b.save_selection.add_callback(
            'activated', lambda w: self.save_imlist())
        b.save_selection.set_enabled(False)

        container.add_widget(w, stretch=0)

        # Mosaic evaluation status
        captions = (('Eval Status', 'llabel'), )
        w, b = Widgets.build_info(captions, orientation=orientation)
        self.w.update(b)
        b.eval_status.set_text('')
        container.add_widget(w, stretch=0)

        # Mosaic evaluation progress bar and stop button
        captions = (('Stop', 'button', 'eval pgs', 'progress'), )
        w, b = Widgets.build_info(captions, orientation=orientation)
        self.w.update(b)
        b.stop.add_callback('activated', lambda w: self.eval_intr())
        b.stop.set_enabled(False)
        self.w.btn_intr_eval = b.stop
        container.add_widget(w, stretch=0)

        btns = Widgets.HBox()
        btns.set_spacing(3)

        btn = Widgets.Button('Close')
        btn.add_callback('activated', lambda w: self.close())
        btns.add_widget(btn, stretch=0)
        btn = Widgets.Button('Help')
        btn.add_callback('activated', lambda w: self.help())
        btns.add_widget(btn, stretch=0)
        btns.add_widget(Widgets.Label(''), stretch=1)
        container.add_widget(btns, stretch=0)

        self.recreate_imlist()
        self.gui_up = True

    def recreate_imlist(self):
        """Refresh image list for new selection."""
        if not self.gui_up:
            return

        treedict = Bunch.caselessDict()
        for imname in self._imlist:
            treedict[imname] = Bunch.Bunch(IMAGE=imname)
        self.treeview.set_tree(treedict)

    def auto_mosaic(self):
        """Create new mosaic using image list from Contents."""
        astroimage_obj = AstroImage()
        self._imlist = {}

        # Get image list from Contents, excluding other mosaics
        file_dict = self.list_plugin_obj.name_dict[self.chname]
        for bnch in itervalues(file_dict):
            if ((not isinstance(bnch, Bunch.Bunch)) or
                    ('mosaic' in bnch.NAME.lower())):
                continue

            # Calculate image footprint, counter-clockwise from
            # bottom-left. Format is [[X1, Y1], ..., [X4, Y4]]
            imname = bnch.NAME
            impath = bnch.path
            datasrc = self.chinfo.datasrc
            if imname in datasrc:
                image = datasrc[imname]
            else:
                image = astroimage_obj
                image.load_file(impath)
            footprint = image.wcs.wcs.calc_footprint()
            self._imlist[imname] = Bunch.Bunch(
                footprint=footprint, path=impath)

        self.recreate_imlist()

        if len(self._imlist) == 0:
            s = 'No images available for mosaic'
            self.logger.error(s)
            self.update_status(s)
            return True

        # Always start a new mosaic.
        # Remove duplicates in case an image have multiple extensions opened.
        images = list(set([bnch.path for bnch in itervalues(self._imlist)]))
        self.fv.nongui_do(self.fv.error_wrap, self.mosaic, images,
                          new_mosaic=True)
        self.fitsimage.auto_levels()

        # Only allow this to happen once, otherwise footprint highlighting
        # gets confusing.
        self.w.create_mosaic.set_enabled(False)

        return True

    # Re-implemented parent method
    def drop_cb(self, canvas, paths):
        """Add given images to mosaic."""
        for path in paths:
            image = self.fv.load_image(path)
            info = self.chinfo.get_image_info(image.get('name'))
            self.add_image_cb(self.fv, self.chname, image, info)
        return True

    def add_image_cb(self, viewer, chname, image, image_info):
        """Add an image to the mosaic."""
        header = image.get_header()

        # Do not add mosaic to another mosaic
        if header.get('OBJECT', 'N/A') == 'MOSAIC':
            return True

        imname = image.get('name', 'NoName')
        impath = image.get('path')
        msg = 'Adding {0} to mosaic'.format(imname)
        new_mosaic = self.settings.get('drop_creates_new_mosaic', False)
        self.fitsimage.onscreen_message(msg, delay=2.0)
        self.fv.nongui_do(self.fv.error_wrap, self.mosaic, [impath],
                          new_mosaic=new_mosaic)
        self.fitsimage.auto_levels()

        # Calculate image footprint, counter-clockwise from bottom-left.
        # Format is [[X1, Y1], ..., [X4, Y4]]
        footprint = image.wcs.wcs.calc_footprint()
        self._imlist[imname] = Bunch.Bunch(footprint=footprint, path=impath)

        self.recreate_imlist()

        self.logger.info('{0} added to mosaic'.format(imname))
        return True

    def draw_footprint_cb(self, w, res_dict):
        """Display selected footprint(s)."""
        if not self.gui_up:
            return True

        self.w.save_selection.set_enabled(False)

        # Clear existing footprint
        if self.footprintstag:
            try:
                self.canvas.delete_object_by_tag(
                    self.footprintstag, redraw=True)
            except Exception:
                pass

        if self.img_mosaic is None or len(res_dict) < 1:
            return True

        # Get mosaic WCS
        header = self.img_mosaic.get_header()
        w = WCS(header)

        # Create footprint of each image
        fpcolor = self.settings.get('footprintscolor', 'red')
        fpwidth = self.settings.get('footprintlinewidth', 5)
        polygonlist = []
        for imname in res_dict:
            self.logger.debug('Drawing footprint for {0}'.format(imname))
            bnch = self._imlist.get(imname, None)
            if bnch is None or bnch.footprint is None:
                continue
            pixcrd = w.wcs_world2pix(bnch.footprint, self._wcs_origin)
            polygonlist.append(
                self.dc.Polygon(pixcrd, color=fpcolor, linewidth=fpwidth))

        # Draw footprint(s) on canvas
        if len(polygonlist) > 0:
            self.footprintstag = self.canvas.add(
                self.dc.CompoundObject(*polygonlist))
            self.w.save_selection.set_enabled(True)

        return True

    def get_selected_paths(self):
        """Return a list of selected image paths."""
        return sorted(
            [self._imlist[key].path for key in self.treeview.get_selected()])

    def save_imlist(self):
        """Save selected image filename(s) to a plain text file.
        If no image selected, no output is generated.

        This can be re-implemented by sub-class if a different
        output format is needed.

        """
        imlist = self.get_selected_paths()

        if len(imlist) == 0:
            s = 'No image selected!'
            self.logger.error(s)
            self.update_status(s)
            return

        fname = Widgets.SaveDialog(
            title='Save image list', selectedfilter='*.txt').get_path()
        if isinstance(fname, tuple):
            fname = fname[0]
        if not fname:  # Cancel
            return
        if os.path.exists(fname):
            s = '{0} will be overwritten'.format(fname)
            self.logger.warn(s)
        ascii.write(
            [imlist], fname, names=['IMAGE'], format='commented_header')
        s = 'Image list saved'
        self.logger.info(s)
        self.update_status(s)

    def remove_mosaic(self):
        """Clear and reset."""
        msg = 'Removed mosaic'
        self.img_mosaic = None
        self.footprintstag = None
        self._imlist.clear()
        self.recreate_imlist()
        self.update_status(msg)
        self.logger.debug(msg)

        if self.gui_up:
            self.canvas.delete_all_objects()

    # Re-implemented parent method
    def start(self):
        """Start the plugin but do not let user create auto mosaic if
        there is already a mosaic."""
        # insert layer if it is not already
        p_canvas = self.fitsimage.get_canvas()
        try:
            p_canvas.get_object_by_tag(self.layertag)
        except KeyError:
            # Add canvas layer
            p_canvas.add(self.canvas, tag=self.layertag)

        # Detect previously generated mosaic
        has_mosaic = False
        for key in self.list_plugin_obj.name_dict[self.chname]:
            if key.startswith('mosaic'):
                has_mosaic = True
                break
        if has_mosaic:
            self.w.create_mosaic.set_enabled(False)
            self.update_status('Some mosaic already exists')
        else:
            self.w.create_mosaic.set_enabled(True)
            self.update_status('')

        self.resume()

    def __str__(self):
        return 'mosaicauto'


# Replace module docstring with config doc for auto insert by Sphinx.
# In the future, if we need the real docstring, we can append instead of
# overwrite.
__doc__ = generate_cfg_example('plugin_Mosaic', package='stginga')
