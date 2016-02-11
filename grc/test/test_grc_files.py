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

import os
from glob import glob

from ..core.Platform import Platform


def test_from_file():
    platform = Platform()

    test_data_directory = os.path.dirname(__file__)

    for file_path in glob('{}/*-xml'.format(test_data_directory)):
        print(file_path)
        try:
            flow_graph = platform.get_new_flow_graph()
            flow_graph.grc_file_path = file_path
            # Other, nested hier_blocks might be auto-loaded here
            flow_graph.import_data(platform.parse_flow_graph(file_path))
            flow_graph.rewrite()
            flow_graph.validate()
            if not flow_graph.is_valid():
                raise Exception('Flowgraph invalid')
        except Exception as e:
            raise
            return False

        generator = platform.Generator(flow_graph, file_path)
        generator.write()