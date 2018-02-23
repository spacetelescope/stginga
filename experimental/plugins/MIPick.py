"""Multi-Image Pick plugin for Ginga reference viewer."""

# GINGA
from ginga.rv.plugins.Pick import Pick

# LOCAL
from stginga.plugins.MultiImage import Region

__all__ = []


class MIPick(Pick):
    """This is like ``Pick`` plugin but modified to work with ``MultiImage``
    plugin."""
    def __init__(self, fv, fitsimage):
        # superclass defines some variables for us, like logger
        super(MIPick, self).__init__(fv, fitsimage)

        # Override parent attributes
        self.layertag = 'mipick-canvas'
        self._textlabel = 'MIPick'

        # Additional attributes
        self.multiimage_name = 'MultiImage'
        self.region = None

    def resume(self):
        super(MIPick, self).resume()

        # Setup the region
        if self.region is None:
            self.region = Region()
            self.region.coord = 'wcs'
            self.region.image = self.fitsimage.get_image()

        # See if multiimage is active
        opmon = self.chinfo.opmon
        multiimage = None
        if opmon.is_active(self.multiimage_name):
            try:
                multiimage = opmon.getPlugin(self.multiimage_name)
            except Exception:
                multiimage = None
            else:
                multiimage.region = self.region
        self.multiimage = multiimage

    def redo(self):
        if self.picktag is None:
            return

        serialnum = self.bump_serial()
        self.ev_intr.set()

        fig = self.canvas.get_object_by_tag(self.picktag)
        if fig.kind != 'compound':
            return True
        bbox = fig.objects[0]
        self.region.image = self.fitsimage.get_image()
        self.draw_compound(bbox, self.canvas, *self.region.bbox(coord='data'))
        fig = self.canvas.getObjectByTag(self.picktag)
        bbox = fig.objects[0]

        # set the pick image to have the same cut levels and transforms
        self.fitsimage.copy_attributes(self.pickimage,
                                       ['transforms', 'cutlevels', 'rgbmap'])

        try:
            # Get other parts of the indicator
            point = fig.objects[1]
            text = fig.objects[2]

            # sanity check on region
            width = bbox.x2 - bbox.x1
            height = bbox.y2 - bbox.y1
            if (width > self.max_side) or (height > self.max_side):
                errmsg = "Image area (%dx%d) too large!" % (width, height)
                self.fv.show_error(errmsg)
                raise Exception(errmsg)

            # Cut and show pick image in pick window
            self.logger.debug("bbox %f,%f %f,%f" % (bbox.x1, bbox.y1,
                                                    bbox.x2, bbox.y2))
            x1, y1, x2, y2, data = self.cutdetail(self.fitsimage,
                                                  self.pickimage,
                                                  int(bbox.x1), int(bbox.y1),
                                                  int(bbox.x2), int(bbox.y2))
            self.logger.debug("cut box %f,%f %f,%f" % (x1, y1, x2, y2))

            # calculate center of pick image
            wd, ht = self.pickimage.get_data_size()
            xc = wd // 2
            yc = ht // 2
            if self.pickcenter is None:
                p_canvas = self.pickimage.get_canvas()
                tag = p_canvas.add(self.dc.Point(xc, yc, 5,
                                                 linewidth=1, color='red'))
                self.pickcenter = p_canvas.get_object_by_tag(tag)

            self.pick_x1, self.pick_y1 = x1, y1
            self.pick_data = data
            self.wdetail.sample_area.set_text('%dx%d' % (x2 - x1, y2 - y1))

            point.color = 'red'
            text.text = '{0}: calc'.format(self._textlabel)
            self.pickcenter.x = xc
            self.pickcenter.y = yc
            self.pickcenter.color = 'red'

            # clear contour and fwhm plots
            if self.have_mpl:
                self.clear_contours()
                self.clear_fwhm()
                self.clear_radial()

            # If multiimage, redo there also.
            try:
                self.multiimage.redo()
            except Exception:
                """Doesn't matter"""
                pass

            # Delete previous peak marks
            objs = self.canvas.getObjectsByTagpfx('peak')
            self.canvas.delete_objects(objs)

            # Offload this task to another thread so that GUI remains
            # responsive
            self.fv.nongui_do(self.search, serialnum, data,
                              x1, y1, wd, ht, fig)

        except Exception as e:
            self.logger.error("Error calculating quality metrics: %s" % (
                str(e)))
            return True

    def draw_cb(self, canvas, tag):
        obj = canvas.getObjectByTag(tag)
        self.draw_compound(obj, canvas)
        return self.redo()

    def edit_cb(self, canvas, obj):
        if obj.kind != 'rectangle':
            return True

        # Get the compound object that sits on the canvas.
        # Make sure edited rectangle was our pick rectangle.
        c_obj = self.canvas.get_object_by_tag(self.picktag)
        if ((c_obj.kind != 'compound') or (len(c_obj.objects) < 3) or
                (c_obj.objects[0] != obj)):
            return False

        # determine center of rectangle
        x1, y1, x2, y2 = obj.get_llur()
        x = x1 + (x2 - x1) // 2
        y = y1 + (y2 - y1) // 2

        # reposition other elements to match
        point = c_obj.objects[1]
        point.x, point.y = x, y
        text = c_obj.objects[2]
        text.x, text.y = x1, y2 + 4

        self.regions.set_bbox(x1, y1, x2, y2, coord='data')

        return self.redo()

    def reset_region(self):
        self.dx = region_default_width
        self.dy = region_default_height

        obj = self.canvas.get_object_by_tag(self.picktag)
        if obj.kind != 'compound':
            return True
        bbox = obj.objects[0]

        # calculate center of bbox
        wd = bbox.x2 - bbox.x1
        dw = wd // 2
        ht = bbox.y2 - bbox.y1
        dh = ht // 2
        x, y = bbox.x1 + dw, bbox.y1 + dh

        # calculate new coords
        bbox.x1, bbox.y1, bbox.x2, bbox.y2 = (x - self.dx, y - self.dy,
                                              x + self.dx, y + self.dy)

        self.regions.set_bbox(bbox.x1, bbox.y1,
                              bbox.x2, bbox.y2, coord='data')

        self.redo()

    def draw_compound(self, obj, canvas, *args):
        """Draw the pick info box."""
        if obj.kind != 'rectangle':
            return True
        canvas.deleteObject(obj)

        if self.picktag:
            try:
                canvas.deleteObjectByTag(self.picktag)
            except Exception:
                pass

        # Get rectangle:
        if len(args) == 4:
            x1, y1, x2, y2 = args
        else:
            x1, y1, x2, y2 = obj.get_llur()

        # determine center of rectangle
        x = x1 + (x2 - x1) // 2
        y = y1 + (y2 - y1) // 2

        tag = canvas.add(self.dc.CompoundObject(
            self.dc.Rectangle(x1, y1, x2, y2, color=self.pickcolor),
            self.dc.Point(x, y, 10, color='red'),
            self.dc.Text(x1, y2 + 4, '{0}: calc'.format(self._textlabel),
                         color=self.pickcolor)))
        self.picktag = tag
        self.region.set_bbox(x1, y1, x2, y2, coord='data')

    def __str__(self):
        return 'mipick'
