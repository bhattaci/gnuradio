"""
Copyright 2007, 2008, 2009 Free Software Foundation, Inc.
This file is part of GNU Radio

GNU Radio Companion is free software; you can redistribute it and/or
modify it under the terms of the GNU General Public License
as published by the Free Software Foundation; either version 2
of the License, or (at your option) any later version.

GNU Radio Companion is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program; if not, write to the Free Software
Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA
"""

from __future__ import absolute_import
import math

from gi.repository import Gtk, PangoCairo, Pango

from . import Actions, Colors, Utils, Constants
from .Element import Element

from ..core.Element import nop_write
from ..core.Port import Port as _Port


class Port(_Port, Element):
    """The graphical port."""

    def __init__(self, parent, direction, **n):
        """
        Port constructor.
        Create list of connector coordinates.
        """
        super(self.__class__, self).__init__(parent, direction, **n)
        Element.__init__(self)
        self._connector_coordinate = (0, 0)
        self._hovering = False
        self.force_show_label = False

        self._area = []
        self._bg_color = self._border_color = 0, 0, 0, 0
        self._font_color = list(Colors.FONT_COLOR)

        self._line_width_factor = 1.0
        self._label_layout_offsets = 0, 0

        self.width_with_label = self.height = 0
        self.connector_length = 0

        self.label_layout = Gtk.DrawingArea().create_pango_layout('')
        self.label_layout.set_alignment(Pango.Alignment.CENTER)

    @property
    def width(self):
        return self.width_with_label if self._show_label else Constants.PORT_LABEL_HIDDEN_WIDTH

    @width.setter
    def width(self, value):
        self.width_with_label = value
        self.label_layout.set_width(value * Pango.SCALE)

    def _update_colors(self):
        """
        Get the color that represents this port's type.
        Codes differ for ports where the vec length is 1 or greater than 1.

        Returns:
            a hex color code.
        """
        if not self.parent_block.enabled:
            self._font_color[-1] = 0.4
            color = Colors.BLOCK_DISABLED_COLOR
        else:
            self._font_color[-1] = 1.0
            color = Colors.PORT_TYPE_TO_COLOR.get(self.get_type()) or Colors.PORT_TYPE_TO_COLOR.get('')
            if self.vlen > 1:
                dark = (0, 0, 30 / 255.0, 50 / 255.0, 70 / 255.0)[min(4,  self.vlen)]
                color = tuple(max(c - dark, 0) for c in color)
        self._bg_color = color
        self._border_color = tuple(max(c - 0.3, 0) for c in color)

    def create_shapes(self):
        """Create new areas and labels for the port."""
        if self.is_horizontal():
            self._area = (0, 0, self.width, self.height)
        elif self.is_vertical():
            self._area = (0, 0, self.height, self.width)
        self.bounds_from_area(self._area)

        self._connector_coordinate = {
            0:   (self.width, self.height / 2),
            90:  (self.height / 2, 0),
            180: (0, self.height / 2),
            270: (self.height / 2, self.width)
        }[self.get_connector_direction()]

    def create_labels(self):
        """Create the labels for the socket."""

        if self.domain in (Constants.GR_MESSAGE_DOMAIN, Constants.DEFAULT_DOMAIN):
            self._line_width_factor = 1.0
        else:
            self._line_width_factor = 2.0

        self._update_colors()

        layout = self.label_layout
        layout.set_markup('<span font_desc="{font}">{name}</span>'.format(
            name=Utils.encode(self.name), font=Constants.PORT_FONT
        ))
        label_width, label_height = self.label_layout.get_pixel_size()

        self.width = 2 * Constants.PORT_LABEL_PADDING + label_width
        self.height = 2 * Constants.PORT_LABEL_PADDING + label_height
        self._label_layout_offsets = [0, Constants.PORT_LABEL_PADDING]
        if self.get_type() == 'bus':
            self.height += Constants.PORT_EXTRA_BUS_HEIGHT
            self._label_layout_offsets[1] += Constants.PORT_EXTRA_BUS_HEIGHT / 2
        self.height += self.height % 2  # uneven height

    def draw(self, widget, cr):
        """
        Draw the socket with a label.
        """
        border_color = self._border_color
        cr.set_line_width(self._line_width_factor * cr.get_line_width())
        cr.translate(*self.coordinate)

        cr.rectangle(*self._area)
        cr.set_source_rgba(*self._bg_color)
        cr.fill_preserve()
        cr.set_source_rgba(*border_color)
        cr.stroke()

        if not self._show_label:
            return  # this port is folded (no label)

        if self.is_vertical():
            cr.rotate(-math.pi / 2)
            cr.translate(-self.width, 0)
        cr.translate(*self._label_layout_offsets)

        cr.set_source_rgba(*self._font_color)
        PangoCairo.update_layout(cr, self.label_layout)
        PangoCairo.show_layout(cr, self.label_layout)

    def get_connector_coordinate(self):
        """
        Get the coordinate where connections may attach to.

        Returns:
            the connector coordinate (x, y) tuple
        """
        return [sum(c) for c in zip(
            self._connector_coordinate,   # relative to port
            self.coordinate,              # relative to block
            self.parent_block.coordinate  # abs
        )]

    def get_connector_direction(self):
        """
        Get the direction that the socket points: 0,90,180,270.
        This is the rotation degree if the socket is an output or
        the rotation degree + 180 if the socket is an input.

        Returns:
            the direction in degrees
        """
        if self.is_source:
            return self.rotation
        elif self.is_sink:
            return (self.rotation + 180) % 360

    @nop_write
    @property
    def rotation(self):
        return self.parent_block.rotation

    def rotate(self, direction):
        """
        Rotate the parent rather than self.

        Args:
            direction: degrees to rotate
        """
        self.parent_block.rotate(direction)

    def move(self, delta_coor):
        """
        Move the parent rather than self.

        Args:
            delta_corr: the (delta_x, delta_y) tuple
        """
        self.parent_block.move(delta_coor)

    @property
    def highlighted(self):
        return self.parent_block.highlighted

    @highlighted.setter
    def highlighted(self, value):
        self.parent_block.highlighted = value

    @property
    def _show_label(self):
        """
        Figure out if the label should be hidden

        Returns:
            true if the label should not be shown
        """
        return self._hovering or self.force_show_label or not Actions.TOGGLE_AUTO_HIDE_PORT_LABELS.get_active()

    def mouse_over(self):
        """
        Called from flow graph on mouse-over
        """
        changed = not self._show_label
        self._hovering = True
        return changed

    def mouse_out(self):
        """
        Called from flow graph on mouse-out
        """
        label_was_shown = self._show_label
        self._hovering = False
        return label_was_shown != self._show_label
