"""ChangeHistory global plugin for Ginga."""
from __future__ import (absolute_import, division, print_function,
                        unicode_literals)

# THIRD-PARTY
from astropy.extern.six import iteritems

# GINGA
from ginga import GingaPlugin
from ginga.gw import Widgets
from ginga.misc import Bunch

__all__ = []


class ChangeHistory(GingaPlugin.GlobalPlugin):
    """Keep track of buffer change history.

    History should stay no matter what channel or image is active.
    New history can be added, but old history cannot be deleted,
    unless the image/channel itself is deleted.

    """
    def __init__(self, fv):
        # superclass defines some variables for us, like logger
        super(ChangeHistory, self).__init__(fv)

        self.columns = [ ('Timestamp', 'MODIFIED'),
                         ('Description', 'DESCRIP'),
                         ]
        # For table-of-contents pane
        self.name_dict = Bunch.caselessDict()
        self.treeview = None

        prefs = self.fv.get_preferences()
        self.settings = prefs.createCategory('plugin_ChangeHistory')
        self.settings.addDefaults(always_expand=True,
                                  color_alternate_rows=True)
        self.settings.load(onError='silent')

        fv.add_callback('image-modified', self.image_modified_cb)
        fv.add_callback('remove-image', self.remove_image_cb)
        fv.add_callback('delete-channel', self.delete_channel_cb)

        self.gui_up = False

    def build_gui(self, container):
        """This method is called when the plugin is invoked.  It builds the
        GUI used by the plugin into the widget layout passed as
        ``container``.

        This method could be called several times if the plugin is opened
        and closed.

        """
        top = Widgets.VBox()
        top.set_border_width(4)

        vbox, sw, self.orientation = Widgets.get_oriented_box(container)
        vbox.set_border_width(4)
        vbox.set_spacing(2)

        # create the Treeview
        always_expand = self.settings.get('always_expand', True)
        color_alternate = self.settings.get('color_alternate_rows', True)
        treeview = Widgets.TreeView(auto_expand=always_expand,
                                    sortable=True,
                                    use_alt_row_color=color_alternate)
        self.treeview = treeview
        treeview.setup_table(self.columns, 3, 'MODIFIED')
        treeview.add_callback('selected', self.show_more)
        vbox.add_widget(treeview, stretch=1)

        fr = Widgets.Frame('Selected History')
        captions = (('History Details', 'textarea'), )
        w, b = Widgets.build_info(captions)
        self.w.update(b)

        b.history_details.set_editable(False)
        b.history_details.set_wrap(True)
        b.history_details.set_text('')
        b.history_details.set_tooltip('Displays selected history entry')

        fr.set_widget(w)
        vbox.add_widget(fr, stretch=0)

        top.add_widget(sw, stretch=1)
        container.add_widget(top, stretch=1)

        self.gui_up = True

    def stop(self):
        self.gui_up = False

    def recreate_toc(self):
        self.logger.debug("Recreating table of contents...")
        self.treeview.set_tree(self.name_dict)

    def show_more(self, widget, res_dict):
        chname = list(res_dict.keys())[0]
        img_dict = res_dict[chname]
        imname = list(img_dict.keys())[0]
        entries = img_dict[imname]
        timestamp = list(entries.keys())[0]
        bnch = entries[timestamp]
        descrip = bnch.DESCRIP
        msg = ('Channel: {0}\nImage: {1}\nTimestamp: {2}\n'
               'Description:\n\n{3}'.format(chname, imname, timestamp, descrip))
        self.w.history_details.set_text(msg)

    def image_modified_cb(self, viewer, chname, image, timestamp, reason):
        """Add an entry with image modification info."""
        imname = image.get('name', 'none')

        # Image fell out of cache and lost its history
        if timestamp is None:
            self.remove_image_cb(viewer, chname, imname, image.get('path'))
            return

        # Add info to internal log
        if chname not in self.name_dict:
            self.name_dict[chname] = {}

        fileDict = self.name_dict[chname]

        if imname not in fileDict:
            fileDict[imname] = {}

        # Z: Zulu time, GMT, UTC
        timestamp = timestamp.strftime('%Y-%m-%d %H:%M:%SZ')
        bnch = Bunch.Bunch(CHNAME=chname, NAME=imname, MODIFIED=timestamp,
                           DESCRIP=reason)
        entries = fileDict[imname]

        # timestamp is guaranteed to be unique?
        entries[timestamp] = bnch

        self.logger.debug("Added history for chname='{0}' imname='{1}' "
                          "timestamp='{2}'".format(chname, imname, timestamp))

        if self.gui_up:
            self.recreate_toc()

    def remove_image_cb(self, viewer, chname, name, path):
        """Delete entries related to deleted image."""
        if chname not in self.name_dict:
            return

        fileDict = self.name_dict[chname]

        if name not in fileDict:
            return

        del fileDict[name]
        self.logger.debug('{0} removed from ChangeHistory'.format(name))

        if not self.gui_up:
            return False
        self.recreate_toc()
        self.w.history_details.set_text('')

    def delete_channel_cb(self, viewer, chinfo):
        """Called when a channel is deleted from the main interface.
        Parameter is chinfo (a bunch)."""
        chname = chinfo.name
        del self.name_dict[chname]
        self.logger.debug('{0} removed from ChangeHistory'.format(chname))

        if not self.gui_up:
            return False
        self.recreate_toc()
        self.w.history_details.set_text('')

    def clear(self):
        self.name_dict = Bunch.caselessDict()
        self.recreate_toc()
        self.w.history_details.set_text('')

    def __str__(self):
        return 'changehistory'
