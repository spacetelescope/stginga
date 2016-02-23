"""Multi-Image viewer global plugin for Ginga."""
from __future__ import (absolute_import, division, print_function,
                        unicode_literals)
from ginga.util.six import itervalues

# GINGA
from ginga.GingaPlugin import GlobalPlugin
from ginga.gw import Widgets, Viewers
from ginga.misc import Bunch

# LOCAL
from stginga.region import Region

__all__ = []


class MultiImage(GlobalPlugin):
    """Display the same region from multiple images."""
    def __init__(self, fv):
        # superclass defines some variables for us, like logger
        super(MultiImage, self).__init__(fv)

        # For region selection
        self._def_coords = 'wcs'
        self._coords_options = (('wcs', 'Fix region to sky'),
                                ('data', 'Fix region to pixels'))
        self.region = None

        # Special place in viewer to display postage stamps
        self._pstampsname = 'pstamps'
        self._pstampname = 'pstamp'
        self._pstamps_h = 100
        self._pstamps_bg_color = (0.4, 0.4, 0.4)
        self.pstamps = None

        # Tracks the contents of postage stamps by channel
        self.name_dict = Bunch.caselessDict()
        self.treeview = None
        self.columns = [('Name', 'NAME')]

        # UNTIL HERE - implement now?
        # TODO: Enable user preferences
        #prefs = self.fv.get_preferences()
        #self.settings = prefs.createCategory('plugin_MultiImage')
        #self.settings.addDefaults(something=True)
        #self.settings.load(onError='silent')

        fv.add_callback('add-image', self.add_image_cb)
        fv.add_callback('add-image-info', self.add_image_info_cb)
        fv.add_callback('remove-image', self.remove_image_cb)
        fv.add_callback('delete-channel', self.delete_channel_cb)

        # UNTIL HERE - do we need this? maybe MIPick auto handle this
        #fv.add_callback('channel-change', self.focus_cb)

        self.gui_up = False

    def build_gui(self, container):
        """This method is called when the plugin is invoked.  It builds the
        GUI used by the plugin into the widget layout passed as
        ``container``.

        This method could be called several times if the plugin is opened
        and closed.

        """
        # Setup for options
        vbox, sw, orientation = Widgets.get_oriented_box(container)
        vbox.set_border_width(4)
        vbox.set_spacing(2)

        # Instructions
        msgFont = self.fv.getFont('sansFont', 12)
        tw = Widgets.TextArea(wrap=True, editable=False)
        tw.set_font(msgFont)
        self.tw = tw

        fr = Widgets.Expander('Instructions')
        fr.set_widget(tw)

        # Coordinates
        coords = Widgets.Frame('WCS Reference')
        hbox = Widgets.HBox()
        hbox.set_border_width(4)
        hbox.set_spacing(4)
        for option, tooltip in self._coords_options:
            btn = Widgets.RadioButton(option)
            btn.set_state(option == self._def_coords)
            btn.add_callback(
                'activated',
                lambda widget, state, option=option: self.set_coords(
                    option, state))
            btn.set_tooltip(tooltip)
            hbox.add_widget(btn)
        hbox.add_widget(Widgets.Label(''), stretch=1)
        coords.set_widget(hbox)

        # TreeView to identify postage stamps
        treeview = Widgets.TreeView(auto_expand=True,
                                    sortable=True,
                                    use_alt_row_color=True)
        self.treeview = treeview
        treeview.setup_table(self.columns, 2, 'NAME')

        # TODO: Highlight postage stamp and focus image?
        #treeview.add_callback('selected', self.dosomething)

        # Basic plugin admin buttons
        btns = Widgets.HBox()
        btns.set_spacing(3)

        btn = Widgets.Button('Close')
        btn.add_callback('activated', lambda w: self.close())
        btns.add_widget(btn, stretch=0)
        btns.add_widget(Widgets.Label(''), stretch=1)

        # Layout the options
        vbox.add_widget(fr, stretch=0)
        vbox.add_widget(coords, stretch=0)
        vbox.add_widget(treeview, stretch=1)

        # Layout top level framing
        vtop = Widgets.VBox()
        vtop.set_border_width(4)
        vtop.add_widget(sw, stretch=1)  # Magic: sw contains vbox
        vtop.add_widget(btns, stretch=0)

        # Options completed.
        container.add_widget(vtop, stretch=1)

        # Postage stamps in a special section of viewer
        if self.pstamps is None and self._pstampsname in self.fv.w:
            self.pstamps_frame = self.fv.w[self._pstampsname]

# UNTIL HERE - Use GridBox?

            pstamps = Widgets.HBox()
            pstamps.resize(pstamps.get_size()[0], self._pstamps_h)
            self.pstamps_frame.add_widget(pstamps)
            self.pstamps = pstamps

        self.gui_up = True

    # UNTIL HERE - Rewrite this as needed
    def instructions(self):
        self.tw.set_text("""To add images to the group, simply ensure that the plugin is active and display the image in the main viewer.

Then move, drag, or edit the region from MIPick as needed.

The WCS options select the common frame of reference to use between images.""")

    def redo(self, channel, image):
        """Image changed."""
        if self.region is None:
            #self.logger.info('Pick a region from MIPick local plugin')
            return

        if image is None:
            return

        chname = channel.name
        bnch = self._get_image_bunch(chname, image)

        # If image exists only in memory, do not include.
        if bnch.PATH is None:
            self.logger.error(
                '{0} in {1} has no physical path'.format(bnch.NAME, chname))
            return

        #channel.fitsimage.copy_attributes(
        #    bnch.PSTAMP, ['transforms', 'cutlevels', 'rgbmap'])

        # Ensure region is accurately reflected on displayed image.
        #self.region.image = image

        # Update postage stamps in all images.
        self._sync_pstamps()

    def cutdetail(self, image, x1, y1, x2, y2):
        """Return details of a cutout."""
        data, x1, y1, x2, y2 = image.cutout_adjust(x1, y1, x2, y2)
        return (x1, y1, x2, y2, data)

    def _get_image_bunch(self, chname, image):
        """Return associated Bunch info. Create new one as needed."""
        imname = image.get('name', 'none')

        # Find listing by channel
        if chname not in self.name_dict:
            file_dict = {}
            self.name_dict[chname] = file_dict
        else:
            file_dict = self.name_dict[chname]

        # Image already exists, do nothing
        if imname in file_dict:
            bnch = file_dict[imname]

        # Add new image
        else:
            impath = image.get('path')
            pstamp, w = self.add_pstamp()
            bnch = Bunch.Bunch(
                CHNAME=chname, NAME=imname, PATH=impath, IMAGE=image,
                PSTAMP=pstamp, WIDGET=w)
            file_dict[imname] = bnch

        # Update postage stamps listing
        self.recreate_toc()

        return bnch

    def _sync_pstamps(self):
        """Make all postage stamps display the same region in respective
        images."""
        for chname in self.name_dict:
            file_dict = self.name_dict[chname]

            for bnch in itervalues(file_dict):
                x1, y1, x2, y2 = self.region.bbox(
                    coord='data', image=bnch.IMAGE)
                x1, y1, x2, y2, data = self.cutdetail(
                    bnch.IMAGE, int(x1), int(y1), int(x2), int(y2))
                bnch.PSTAMP.set_data(data)

    def recreate_toc(self):
        """Recreate postage stamps listing."""
        self.logger.debug('Recreating table of contents...')
        self.treeview.set_tree(self.name_dict)

        # Unless there are thousands of postage stamps, this is okay to do.
        self.treeview.set_optimal_column_widths()

    def add_pstamp(self):
        """Add a postage stamp widget."""

# UNTIL HERE - make this like Thumbs.py

        di = Viewers.ImageViewCanvas(logger=self.logger)
        di.set_desired_size(self._pstamps_h, self._pstamps_h)
        di.enable_autozoom('on')
        di.add_callback('configure', self.window_resized_cb)
        di.enable_autocuts('off')
        di.set_bg(*self._pstamps_bg_color)
        di.set_name(self._pstampname)  # for debugging

        iw = Widgets.wrap(di.get_widget())
        self.pstamps.add_widget(iw)

        return di, iw

    def set_region(self, region):
        """Set a shared region. This is called from ``MIPick`` plugin."""
        self.region = region

    def set_coords(self, coords, state):
        """Change coordinate system."""
        if state:
            self.logger.debug('Setting coordinate system to {0}'.format(coords))
            self.region.set_coords(coords)

    def window_resized_cb(self, fitsimage, width, height):
        """Handle resizing of postage stamp widget."""
        self.logger.debug('{0} resized to w={1} h={2}'.format(
            self._pstampname, width, height))
        fitsimage.zoom_fit()

    def add_image_cb(self, viewer, chname, image, image_info):
        """Add an image to postage stamp collection."""
        if not self.gui_up:
            return False

        channel = self.fv.get_channelInfo(chname)
        self.redo(channel, image)

    def add_image_info_cb(self, viewer, channel, image_info):
        """Almost the same as :meth:`add_image_cb`, except that the image
        may not be loaded in memory."""
        try:
            image = channel.get_loaded_image(image_info.name)
        except KeyError:
            image = None

        self.redo(channel, image)

    def remove_image_cb(self, viewer, chname, name, path):
        """Remove image from listing and postage stamp collection."""
        if not self.gui_up:
            return False

        if chname not in self.name_dict:
            return

        file_dict = self.name_dict[chname]

        if name not in file_dict:
            return

        bnch = file_dict[name]
        self.pstamps.remove(bnch.WIDGET)
        del file_dict[name]
        self.recreate_toc()

    def delete_channel_cb(self, viewer, channel):
        """Called when a channel is deleted from the main interface."""
        if not self.gui_up:
            return False

        chname = channel.name

        if chname not in self.name_dict:
            return

        file_dict = self.name_dict[chname]

        for name in file_dict:
            bnch = file_dict[name]
            self.pstamps.remove(bnch.WIDGET)

        del self.name_dict[chname]
        self.recreate_toc()

    def start(self):
        """Start the global plugin."""
        self.instructions()
        self.pstamps_frame.show()
        self.recreate_toc()

    def stop(self):
        """Clean up."""
        self.gui_up = False
        self.fv.showStatus('')

        # Remove all displayed postage stamps.
        self.pstamps_frame.remove(self.pstamps, delete=True)
        self.pstamps = None

        self.name_dict.clear()

    def close(self):
        """Close the global plugin."""
        self.fv.stop_global_plugin(str(self))
        return True

    def __str__(self):
        return 'multiimage'
