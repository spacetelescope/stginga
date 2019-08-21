"""
Mosaic with option to highlight individual component.

**Plugin Type: Local**

``MosaicAuto`` is a local plugin, which means it is associated with a
channel. An instance can be opened for each channel.

**Usage**

.. warning:: This can be very memory intensive.

This plugin is used to automatically create a mosaic of all currently
loaded images in the channel. The position of an image on the mosaic is
determined by its WCS without distortion correction. This is meant as a
quick-look tool, not an `AstroDrizzle <http://drizzlepac.stsci.edu/>`_
replacement. Currently, such a mosaic can only be created once per Ginga
session.

Once the mosaic is successfully created, user can select the desired
image name(s) to highlight associated footprint(s) on the mosaic.
Alternately, user can also click directly on the displayed mosaic to
highlight a footprint; Clicking on a highlighted footprint again will
un-highlight it.

A shortlist of only the selected image names are displayed under the "Selected"
tab. This list can be saved to a file by clicking "Save Selection" button.
Optionally, the mosaic itself can be saved using
:ref:`ginga:sec-plugins-global-saveimage`.

"""
# STDLIB
import os

# THIRD-PARTY
from astropy.io import ascii
from astropy.wcs import WCS

# GINGA
from ginga.gw import Widgets
from ginga.misc import Bunch
from ginga.rv.plugins.Mosaic import Mosaic

# STGINGA
from stginga.plugins.local_plugin_mixin import HelpMixin
from stginga.utils import GINGA_LT_3

__all__ = ['MosaicAuto']


class MosaicAuto(HelpMixin, Mosaic):

    def __init__(self, fv, fitsimage):
        super(MosaicAuto, self).__init__(fv, fitsimage)

        self.help_url = ('http://stginga.readthedocs.io/en/latest/stginga/'
                         'plugins_manual/mosaicauto.html')

        # To store individual images and their footprints
        self._wcs_origin = 0
        self._imlist = {}
        self.imlist_columns = [('Image', 'IMAGE')]
        self.footprintstag = None
        self._recreate_fp = True

        self.list_plugin_obj = self.fv.gpmon.get_plugin('Contents')

        # Enable selection from canvas
        self.canvas.set_callback('cursor-down', self.hl_canvas2table)

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

        nb = Widgets.TabWidget()
        container.add_widget(nb, stretch=1)

        self.treeview = Widgets.TreeView(auto_expand=True,
                                         sortable=True,
                                         selection='multiple',
                                         use_alt_row_color=True)
        self.treeview.setup_table(self.imlist_columns, 1, 'IMAGE')
        self.treeview.add_callback('selected', self.draw_footprint_cb)
        nb.add_widget(self.treeview, title='All')

        self.treeviewsel = Widgets.TreeView(auto_expand=True,
                                            sortable=True,
                                            use_alt_row_color=True)
        self.treeviewsel.setup_table(self.imlist_columns, 1, 'IMAGE')
        nb.add_widget(self.treeviewsel, title='Selected')

        captions = (('Create Mosaic', 'button'),
                    ('Select All', 'button', 'Deselect All', 'button',
                     'Spacer1', 'spacer'),
                    ('Save Selection', 'button'))
        w, b = Widgets.build_info(captions, orientation=orientation)
        self.w.update(b)

        # DO NOT REALLY NEED THIS WHEN add-image CALLBACK WORKS AGAIN
        b.create_mosaic.set_tooltip(
            'Build mosaic from currently opened images')
        b.create_mosaic.add_callback('activated', lambda w: self.auto_mosaic())

        b.select_all.set_tooltip('Select all footprints')
        b.select_all.add_callback('activated', lambda w: self.select_all_cb())
        b.select_all.set_enabled(False)

        b.deselect_all.set_tooltip('Clear selection')
        b.deselect_all.add_callback(
            'activated', lambda w: self.deselect_all_cb())
        b.deselect_all.set_enabled(False)

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

        self.gui_up = True

    def auto_mosaic(self):
        """Create new mosaic using image list from Contents."""
        if GINGA_LT_3:
            from ginga.AstroImage import AstroImage
            astroimage_obj = AstroImage()
        else:
            from ginga.util.io_fits import load_file

        self._imlist = {}
        self._recreate_fp = True
        self.treeview.clear()
        self.treeviewsel.clear()

        # Get image list from Contents, excluding other mosaics
        file_dict = self.list_plugin_obj.name_dict[self.chname]
        for bnch in file_dict.values():
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
            elif GINGA_LT_3:
                image = astroimage_obj
                image.load_file(impath)
            else:
                image = load_file(impath)
            footprint = image.wcs.wcs.calc_footprint()  # Astropy only?
            self._imlist[imname] = Bunch.Bunch(
                footprint=footprint, path=impath)

        if len(self._imlist) == 0:
            s = 'No images available for mosaic'
            self.logger.error(s)
            self.update_status(s)
            return True

        # Always start a new mosaic.
        # Remove duplicates in case an image have multiple extensions opened.
        images = list(set([bnch.path for bnch in self._imlist.values()]))
        self.fv.nongui_do(self.fv.error_wrap, self.mosaic, images,
                          new_mosaic=True)
        self.fitsimage.auto_levels()

        # Only allow this to happen once, otherwise footprint highlighting
        # gets confusing.
        self.w.create_mosaic.set_enabled(False)

        self.w.select_all.set_enabled(True)
        self.w.deselect_all.set_enabled(True)

        # Populate table listing.
        treedict = Bunch.caselessDict()
        for imname in self._imlist:
            treedict[imname] = Bunch.Bunch(IMAGE=imname)
        self.treeview.set_tree(treedict)

        return True

    def _create_footprint_obj(self):
        """Create a compound object containing all footprint polygons."""

        # Nothing has changed
        if not self._recreate_fp:
            return

        # Clear existing footprint
        if self.footprintstag:
            try:
                self.canvas.delete_object_by_tag(
                    self.footprintstag, redraw=True)
            except Exception:
                pass

        # No mosaic created; nothing to do.
        if self.img_mosaic is None:
            self.logger.error('Mosaic is not found, cannot create polygons')
            return

        # Get mosaic WCS
        header = self.img_mosaic.get_header()
        w = WCS(header)

        # Create footprint of each image
        fpcolor = self.settings.get('footprintscolor', 'red')
        fpwidth = self.settings.get('footprintlinewidth', 5)
        polygonlist = []
        for imname, bnch in self._imlist.items():
            self.logger.debug('Drawing footprint for {0}'.format(imname))
            if bnch.footprint is None:
                continue
            pixcrd = w.wcs_world2pix(bnch.footprint, self._wcs_origin)
            obj = self.dc.Polygon(pixcrd, color=fpcolor, linewidth=fpwidth,
                                  alpha=0)  # Hide until selected
            obj.imname = imname  # Needed for selection
            polygonlist.append(obj)

        if len(polygonlist) > 0:
            self.footprintstag = self.canvas.add(
                self.dc.CompoundObject(*polygonlist))
            self.w.select_all.set_enabled(True)
            self.w.deselect_all.set_enabled(True)
        else:
            self.w.select_all.set_enabled(False)
            self.w.deselect_all.set_enabled(False)

        self._recreate_fp = False

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
        self._recreate_fp = True
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
        self._create_footprint_obj()

        # Update table listing
        treedict = Bunch.caselessDict()
        treedict[imname] = Bunch.Bunch(IMAGE=imname)
        self.treeview.add_tree(treedict)

        self.logger.info('{0} added to mosaic'.format(imname))
        return True

    def hl_canvas2table(self, canvas, button, data_x, data_y):
        """Highlight footprint on table when user click on canvas."""

        # Footprints not created properly if done during mosaicking,
        # so create them here if needed.
        self._create_footprint_obj()

        # Nothing to do if no masks are displayed
        try:
            obj = canvas.get_object_by_tag(self.footprintstag)
        except Exception:
            return

        if obj.kind != 'compound':
            return

        # Get existing selection from table listing
        imname_from_table = list(self.treeview.get_selected())
        n = len(imname_from_table)

        # Get selected polygons
        try:
            poly_items = obj.get_items_at(data_x, data_y)
        except TypeError:  # ginga >= 2.6.5
            poly_items = obj.get_items_at((data_x, data_y))

        # Select if not selected and vice versa,
        # also do the same to table listing.
        for poly in poly_items:
            imname = poly.imname
            treepath = (imname, )

            if imname in imname_from_table:  # De-select
                poly.alpha = 0
                n -= 1

                try:
                    self.treeview.select_path(treepath, state=False)
                except TypeError:
                    # Use Qt-specific API; no choice here.
                    # https://github.com/ejeschke/ginga/issues/532
                    item = self.treeview._path_to_item(treepath)
                    item.setSelected(False)

            else:  # Select
                poly.alpha = 1
                n += 1
                self.treeview.select_path(treepath)

        # Refresh selected listing
        self.treeviewsel.set_tree(self.treeview.get_selected())

        if n > 0:
            self.w.save_selection.set_enabled(True)
        else:
            self.w.save_selection.set_enabled(False)

        self.canvas.redraw(whence=3)
        return True

    def draw_footprint_cb(self, w, res_dict):
        """Display selected footprint(s)."""
        self.w.save_selection.set_enabled(False)
        self.treeviewsel.clear()

        # Footprints not created properly if done during mosaicking,
        # so create them here if needed.
        self._create_footprint_obj()

        if self.footprintstag is None:
            return

        try:
            obj = self.canvas.get_object_by_tag(self.footprintstag)
        except Exception as e:
            self.logger.error(str(e))
            return

        if obj.kind != 'compound':
            return

        # Show only selected footprint(s) on canvas.
        n = 0
        for poly in obj.objects:
            if poly.imname in res_dict:
                n += 1
                poly.alpha = 1
            else:
                poly.alpha = 0

        if n > 0:
            self.treeviewsel.set_tree(res_dict)
            # Display highlighted entries only in second table
            self.w.save_selection.set_enabled(True)

        self.canvas.redraw(whence=3)
        return True

    def select_all_cb(self):
        """Highlight all footprints."""
        self.w.save_selection.set_enabled(False)
        self.treeviewsel.clear()

        # Footprints not created properly if done during mosaicking,
        # so create them here if needed.
        self._create_footprint_obj()

        if self.footprintstag is None:
            return

        try:
            obj = self.canvas.get_object_by_tag(self.footprintstag)
        except Exception:
            return

        if obj.kind != 'compound':
            return

        for poly in obj.objects:
            poly.alpha = 1
            self.treeview.select_path((poly.imname, ))

        # Refresh selected listing
        self.treeviewsel.set_tree(self.treeview.get_selected())
        self.w.save_selection.set_enabled(True)

        self.canvas.redraw(whence=3)
        return True

    def deselect_all_cb(self):
        """Clear selection."""
        self.w.save_selection.set_enabled(False)
        self.treeviewsel.clear()
        self.treeview.clear_selection()

        # Footprints not created properly if done during mosaicking,
        # so create them here if needed.
        self._create_footprint_obj()

        if self.footprintstag is None:
            return

        try:
            obj = self.canvas.get_object_by_tag(self.footprintstag)
        except Exception:
            return

        if obj.kind != 'compound':
            return

        for poly in obj.objects:
            poly.alpha = 0

        self.canvas.redraw(whence=3)
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
        if fname is None:  # Cancel
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
        self._recreate_fp = True
        self._imlist = {}
        self.treeview.clear()
        self.treeviewsel.clear()

        self.logger.debug(msg)

        if self.gui_up:
            self.update_status(msg)
            self.w.create_mosaic.set_enabled(True)
            self.w.select_all.set_enabled(False)
            self.w.deselect_all.set_enabled(False)
            self.w.save_selection.set_enabled(False)
            self.canvas.delete_all_objects()
            self.canvas.redraw(whence=3)

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


# Append module docstring with config doc for auto insert by Sphinx.
from ginga.util.toolbox import generate_cfg_example  # noqa
if __doc__ is not None:
    __doc__ += generate_cfg_example('plugin_Mosaic', package='stginga')
