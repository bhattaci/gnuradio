# Copyright 2016 Free Software Foundation, Inc.
# This file is part of GNU Radio
#
# GNU Radio Companion is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# GNU Radio Companion is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA

import gtk


class FlowGraphPagesManager(gtk.HBox):

    def __init__(self):
        gtk.HBox.__init__(self)

        combo_box = self.combo_box = combo_box = gtk.combo_box_new_text()
        self.pack_start(combo_box)

        button = self.button = gtk.Button('...')
        self.pack_start(button, False)

        menu = self.menu = gtk.Menu()

        self.show_all()
        self.flow_graph = None

    def set_flow_graph(self, flow_graph):
        self.flow_graph = flow_graph
        pages = set(block.get_page() for block in flow_graph.iter_blocks())
        active = flow_graph.get_option('_active_page')

        self._update_pages(pages, active)

    def _update_pages(self, pages, active):
        self.combo_box.get_model().clear()
        pages = sorted(pages)
        for page in pages:
            self.combo_box.append_text(page)
        try:
            active_index = pages.index(active)
        except ValueError:
            active_index = 0
        self.combo_box.set_active(active_index)

    def current_page(self):
        return self.combo_box.get_active_text()
