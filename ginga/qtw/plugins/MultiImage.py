from ginga import GingaPlugin
from ginga.gw import Widgets, Viewers


class MultiImage(GingaPlugin.LocalPlugin):
    """Coordinate display between multiple images"""

    def __init__(self, fv, fitsimage):
        super(MultiImage, self).__init__(fv, fitsimage)

        self.logger.debug('Called.')

        self.dc = self.fv.getDrawClasses()

        canvas = self.dc.DrawingCanvas()
        canvas.enable_draw(True)
        canvas.enable_edit(True)
        canvas.set_drawtype('rectangle', color='cyan', linestyle='dash',
                            coord='wcs', drawdims=True)
        canvas.set_callback('draw-event', self.draw_cb)
        canvas.set_callback('edit-event', self.edit_cb)
        canvas.add_draw_mode('move', down=self.btndown,
                             move=self.drag, up=self.update)
        canvas.register_for_cursor_drawing(self.fitsimage)
        canvas.setSurface(self.fitsimage)
        canvas.set_draw_mode('move')
        self.canvas = canvas

        self.layertag = 'muimg-canvas'
        self.dx = 30
        self.dy = 30
        self.max_side = 1024
        self.images = {}
        self.center_ra = None
        self.center_dec = None

    def build_gui(self, container):
        """Build the Dialog"""
        self.logger.debug('Called.')

        # Get container specs.
        vbox, sw, orientation = Widgets.get_oriented_box(container)
        vbox.set_border_width(4)
        vbox.set_spacing(2)

        # Overall container
        vtop = Widgets.VBox()
        vtop.set_border_width(4)
        vtop.add_widget(sw, stretch=1)
        self.vtop = vtop

        # Instructiopns
        self.msgFont = self.fv.getFont("sansFont", 12)
        tw = Widgets.TextArea(wrap=True, editable=False)
        tw.set_font(self.msgFont)
        self.tw = tw

        fr = Widgets.Expander("Instructions")
        fr.set_widget(tw)
        vbox.add_widget(fr, stretch=0)

        container.add_widget(vtop, stretch=1)

    def instructions(self):
        self.tw.set_text('These would be fun instructions.')
        self.tw.set_font(self.msgFont)

    def start(self):
        self.logger.debug('Called.')

        self.instructions()

        # insert layer if it is not already
        p_canvas = self.fitsimage.get_canvas()
        try:
            p_canvas.getObjectByTag(self.layertag)

        except KeyError:
            # Add canvas layer
            p_canvas.add(self.canvas, tag=self.layertag)

        self.redo()

    def resume(self):
        self.logger.debug('Called.')

        self.canvas.ui_setActive(True)
        self.fv.showStatus("Do something")

    def redo(self):
        self.logger.debug('Called.')

        data = self.fitsimage.get_image()
        if data is None:
            return
        try:
            pickimage = self.images[data]
        except KeyError:
            pickimage = self.add_pickimage()
            self.images[data] = pickimage
        self.fitsimage.copy_attributes(pickimage,
                                       ['transforms', 'cutlevels',
                                        'rgbmap'])

        try:
            bbox = self.canvas.getObjectByTag(self.picktag)
            self.logger.debug('bbox="{}"'.format(bbox.get_llur()))
        except AttributeError:
            # No picktag yet, ignore
            return

        # Loop through all images.
        for image in self.images:

            # Determine the region.
            xc, yc = image.radectopix(self.center_ra, self.center_dec)
            x1, y1 = xc - self.dx, yc - self.dy
            x2, y2 = xc + self.dx, yc + self.dy

            # Cut and show pick image in pick window
            x1, y1, x2, y2, data = self.cutdetail(image,
                                                  int(x1), int(y1),
                                                  int(x2), int(y2))
            self.logger.debug("cut box %f,%f %f,%f" % (x1, y1, x2, y2))
            pickimage = self.images[image]
            pickimage.set_data(data)

    def stop(self):
        self.logger.debug('Called.')

        # deactivate the canvas
        self.canvas.ui_setActive(False)
        self.fv.showStatus("")

    def close(self):
        self.logger.debug('Called.')

        chname = self.fv.get_channelName(self.fitsimage)
        self.fv.stop_local_plugin(chname, str(self))
        return True

    def pause(self):
        self.logger.debug('Called.')

        self.canvas.ui_setActive(False)

    def __str__(self):
        return 'multi image'

    def zoomset(self, setting, zoomlevel, fitsimage):
        scalefactor = fitsimage.get_scale()
        self.logger.debug("scalefactor = %.2f" % (scalefactor))
        text = self.fv.scale2text(scalefactor)

    def btndown(self, canvas, event, data_x, data_y, viewer):
        self.set_region(data_x, data_y)
        return True

    def update(self, canvas, event, data_x, data_y, viewer):
        self.set_region(data_x, data_y, finalize=True)
        return self.redo()

    def drag(self, canvas, event, data_x, data_y, viewer):
        self.set_region(data_x, data_y)
        return self.redo()

    def draw_cb(self, canvas, tag):
        self.logger.debug('Called.')
        obj = canvas.getObjectByTag(tag)
        self.logger.debug('obj="{}"'.format(obj))
        pt_obj = canvas.getObjectByTag(self.picktag)
        self.logger.debug('self.picktag="{}"'.format(pt_obj))
        if obj.kind != 'rectangle':
            return True
        canvas.deleteObject(obj)
        x1, y1, x2, y2 = obj.get_llur()
        self.dx = (x2 - x1) // 2
        self.dy = (y2 - y1) // 2
        self.set_region(x1 + self.dx, y1 + self.dy, finalize=True)
        return self.redo()

    def edit_cb(self, canvas, obj):
        self.logger.debug('Called.')
        self.logger.debug('obj="{}"'.format(obj))
        pick_obj = canvas.getObjectByTag(self.picktag)
        self.logger.debug('self.picktag="{}"'.format(pt_obj))
        return self.redo()

    def detailxy(self, canvas, button, data_x, data_y):
        """Motion event in the pick fits window.  Show the pointing
        information under the cursor.
        """
        if button == 0:
            # TODO: we could track the focus changes to make this check
            # more efficient
            fitsimage = self.fv.getfocus_fitsimage()
            # Don't update global information if our fitsimage isn't focused
            if fitsimage != self.fitsimage:
                return True

            # Add offsets from cutout
            data_x = data_x + self.pick_x1
            data_y = data_y + self.pick_y1

            return self.fv.showxy(self.fitsimage, data_x, data_y)

    def cutdetail(self, srcimage, x1, y1, x2, y2):
        data, x1, y1, x2, y2 = srcimage.cutout_adjust(x1, y1, x2, y2)
        return (x1, y1, x2, y2, data)

    def add_pickimage(self):

        # Setup for thumbnail display
        cm, im = self.fv.cm, self.fv.im
        di = Viewers.ImageViewCanvas(logger=self.logger)
        width, height = 200, 200
        di.configure_window(width, height)
        di.enable_autozoom('off')
        di.enable_autocuts('off')
        di.zoom_to(3)
        settings = di.get_settings()
        settings.getSetting('zoomlevel').add_callback('set',
                                                      self.zoomset, di)
        di.set_cmap(cm)
        di.set_imap(im)
        di.set_callback('none-move', self.detailxy)
        di.set_bg(0.4, 0.4, 0.4)
        # for debugging
        di.set_name('pickimage')

        bd = di.get_bindings()
        bd.enable_pan(True)
        bd.enable_zoom(True)
        bd.enable_cuts(True)

        iw = Widgets.wrap(di.get_widget())
        self.vtop.add_widget(iw)

        return di

    def set_region(self, x, y, finalize=False):
        """Set the box"""
        linestyle = 'solid' if finalize else 'dash'
        try:
            obj = self.canvas.getObjectByTag(self.picktag)
        except AttributeError:
            x1, y1 = x - self.dx, y - self.dy
            x2, y2 = x + self.dx, y + self.dy
            self.picktag = self.canvas.add(
                self.dc.Rectangle(x1, y1, x2, y2,
                                  color='cyan',
                                  linestyle=linestyle)
            )
            obj = self.canvas.getObjectByTag(self.picktag)
        else:
            obj.linestyle = linestyle
            obj.x1, obj.y1 = x - self.dx, y - self.dy
            obj.x2, obj.y2 = x + self.dx, y + self.dy
            self.canvas.redraw(whence=3)

            data = self.fitsimage.get_image()
            self.center_ra, self.center_dec = data.pixtoradec(x, y)
