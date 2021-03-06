"""
Copyright 2008-2015 Free Software Foundation, Inc.
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

from six.moves import filter

from .Element import Element, lazy_property

from . import Constants


def _get_source_from_virtual_sink_port(vsp):
    """
    Resolve the source port that is connected to the given virtual sink port.
    Use the get source from virtual source to recursively resolve subsequent ports.
    """
    try:
        return _get_source_from_virtual_source_port(
            vsp.get_enabled_connections()[0].source_port)
    except:
        raise Exception('Could not resolve source for virtual sink port {}'.format(vsp))


def _get_source_from_virtual_source_port(vsp, traversed=[]):
    """
    Recursively resolve source ports over the virtual connections.
    Keep track of traversed sources to avoid recursive loops.
    """
    if not vsp.parent.is_virtual_source():
        return vsp
    if vsp in traversed:
        raise Exception('Loop found when resolving virtual source {}'.format(vsp))
    try:
        return _get_source_from_virtual_source_port(
            _get_source_from_virtual_sink_port(
                list(filter(  # Get all virtual sinks with a matching stream id
                    lambda vs: vs.get_param('stream_id').get_value() == vsp.parent.get_param('stream_id').get_value(),
                    list(filter(  # Get all enabled blocks that are also virtual sinks
                        lambda b: b.is_virtual_sink(),
                        vsp.parent.parent.get_enabled_blocks(),
                    )),
                ))[0].sinks[0]
            ), traversed + [vsp],
        )
    except:
        raise Exception('Could not resolve source for virtual source port {}'.format(vsp))


def _get_sink_from_virtual_source_port(vsp):
    """
    Resolve the sink port that is connected to the given virtual source port.
    Use the get sink from virtual sink to recursively resolve subsequent ports.
    """
    try:
        # Could have many connections, but use first
        return _get_sink_from_virtual_sink_port(
            vsp.get_enabled_connections()[0].sink_port)
    except:
        raise Exception('Could not resolve source for virtual source port {}'.format(vsp))


def _get_sink_from_virtual_sink_port(vsp, traversed=[]):
    """
    Recursively resolve sink ports over the virtual connections.
    Keep track of traversed sinks to avoid recursive loops.
    """
    if not vsp.parent.is_virtual_sink():
        return vsp
    if vsp in traversed:
        raise Exception('Loop found when resolving virtual sink {}'.format(vsp))
    try:
        return _get_sink_from_virtual_sink_port(
            _get_sink_from_virtual_source_port(
                filter(  # Get all virtual source with a matching stream id
                    lambda vs: vs.get_param('stream_id').get_value() == vsp.parent.get_param('stream_id').get_value(),
                    list(filter(  # Get all enabled blocks that are also virtual sinks
                        lambda b: b.is_virtual_source(),
                        vsp.parent.parent.get_enabled_blocks(),
                    )),
                )[0].sources[0]
            ), traversed + [vsp],
        )
    except:
        raise Exception('Could not resolve source for virtual sink port {}'.format(vsp))


class Port(Element):

    is_port = True
    is_clone = False

    def __init__(self, parent, direction, **n):
        """
        Make a new port from nested data.

        Args:
            block: the parent element
            n: the nested odict
            dir: the direction
        """
        self._n = n
        if n['type'] == 'message':
            n['domain'] = Constants.GR_MESSAGE_DOMAIN

        if 'domain' not in n:
            n['domain'] = Constants.DEFAULT_DOMAIN
        elif n['domain'] == Constants.GR_MESSAGE_DOMAIN:
            n['key'] = n['name']
            n['type'] = 'message'  # For port color

        # Build the port
        Element.__init__(self, parent)
        # Grab the data
        self.name = n['name']
        self.key = n['key']
        self.domain = n.get('domain')
        self._type = n.get('type', '')
        self.inherit_type = not self._type
        self._hide = n.get('hide', '')
        self._dir = direction
        self._hide_evaluated = False  # Updated on rewrite()

        self._nports = n.get('nports', '')
        self._vlen = n.get('vlen', '')
        self._optional = bool(n.get('optional'))
        self.clones = []  # References to cloned ports (for nports > 1)

    def __str__(self):
        if self.is_source:
            return 'Source - {}({})'.format(self.name, self.key)
        if self.is_sink:
            return 'Sink - {}({})'.format(self.name, self.key)

    def validate(self):
        Element.validate(self)
        if self.get_type() not in Constants.TYPE_TO_SIZEOF.keys():
            self.add_error_message('Type "{}" is not a possible type.'.format(self.get_type()))
        platform = self.parent_platform
        if self.domain not in platform.domains:
            self.add_error_message('Domain key "{}" is not registered.'.format(self.domain))
        if not self.get_enabled_connections() and not self.get_optional():
            self.add_error_message('Port is not connected.')

    def rewrite(self):
        """
        Handle the port cloning for virtual blocks.
        """
        if self.inherit_type:
            try:
                # Clone type and vlen
                source = self.resolve_empty_type()
                self._type = str(source.get_type())
                self._vlen = str(source.get_vlen())
            except:
                # Reset type and vlen
                self._type = ''
                self._vlen = ''

        Element.rewrite(self)
        hide = self.parent.resolve_dependencies(self._hide).strip().lower()
        self._hide_evaluated = False if hide in ('false', 'off', '0') else bool(hide)

        # Update domain if was deduced from (dynamic) port type
        type_ = self.get_type()
        if self.domain == Constants.GR_STREAM_DOMAIN and type_ == "message":
            self.domain = Constants.GR_MESSAGE_DOMAIN
            self.key = self.name
        if self.domain == Constants.GR_MESSAGE_DOMAIN and type_ != "message":
            self.domain = Constants.GR_STREAM_DOMAIN
            self.key = '0'  # Is rectified in rewrite()

    def resolve_virtual_source(self):
        if self.parent.is_virtual_sink():
            return _get_source_from_virtual_sink_port(self)
        if self.parent.is_virtual_source():
            return _get_source_from_virtual_source_port(self)

    def resolve_empty_type(self):
        if self.is_sink:
            try:
                src = _get_source_from_virtual_sink_port(self)
                if not src.inherit_type:
                    return src
            except:
                pass
            sink = _get_sink_from_virtual_sink_port(self)
            if not sink.inherit_type:
                return sink
        if self.is_source:
            try:
                src = _get_source_from_virtual_source_port(self)
                if not src.inherit_type:
                    return src
            except:
                pass
            sink = _get_sink_from_virtual_source_port(self)
            if not sink.inherit_type:
                return sink

    def get_vlen(self):
        """
        Get the vector length.
        If the evaluation of vlen cannot be cast to an integer, return 1.

        Returns:
            the vector length or 1
        """
        vlen = self.parent.resolve_dependencies(self._vlen)
        try:
            return max(1, int(self.parent_flowgraph.evaluate(vlen)))
        except:
            return 1

    def get_nports(self):
        """
        Get the number of ports.
        If already blank, return a blank
        If the evaluation of nports cannot be cast to a positive integer, return 1.

        Returns:
            the number of ports or 1
        """
        if self._nports == '':
            return 1

        nports = self.parent.resolve_dependencies(self._nports)
        try:
            return max(1, int(self.parent_flowgraph.evaluate(nports)))
        except:
            return 1

    def get_optional(self):
        return bool(self._optional)

    def add_clone(self):
        """
        Create a clone of this (master) port and store a reference in self._clones.

        The new port name (and key for message ports) will have index 1... appended.
        If this is the first clone, this (master) port will get a 0 appended to its name (and key)

        Returns:
            the cloned port
        """
        # Add index to master port name if there are no clones yet
        if not self.clones:
            self.name = self._n['name'] + '0'
            # Also update key for none stream ports
            if not self.key.isdigit():
                self.key = self.name

        name = self._n['name'] + str(len(self.clones) + 1)
        # Dummy value 99999 will be fixed later
        key = '99999' if self.key.isdigit() else name

        # Clone
        port_factory = self.parent_platform.get_new_port
        port = port_factory(self.parent, direction=self._dir,
                            name=name, key=key,
                            master=self, cls_key='clone')

        self.clones.append(port)
        return port

    def remove_clone(self, port):
        """
        Remove a cloned port (from the list of clones only)
        Remove the index 0 of the master port name (and key9 if there are no more clones left
        """
        self.clones.remove(port)
        # Remove index from master port name if there are no more clones
        if not self.clones:
            self.name = self._n['name']
            # Also update key for none stream ports
            if not self.key.isdigit():
                self.key = self.name

    @lazy_property
    def is_sink(self):
        return self._dir == 'sink'

    @lazy_property
    def is_source(self):
        return self._dir == 'source'

    def get_type(self):
        return self.parent_block.resolve_dependencies(self._type)

    def get_hide(self):
        return self._hide_evaluated

    def get_connections(self):
        """
        Get all connections that use this port.

        Returns:
            a list of connection objects
        """
        connections = self.parent_flowgraph.connections
        connections = [c for c in connections if c.source_port is self or c.sink_port is self]
        return connections

    def get_enabled_connections(self):
        """
        Get all enabled connections that use this port.

        Returns:
            a list of connection objects
        """
        return [c for c in self.get_connections() if c.enabled]

    def get_associated_ports(self):
        if not self.get_type() == 'bus':
            return [self]

        block = self.parent_block
        if self.is_source:
            block_ports = block.sources
            bus_structure = block.current_bus_structure['source']
        else:
            block_ports = block.sinks
            bus_structure = block.current_bus_structure['sink']

        ports = [i for i in block_ports if not i.get_type() == 'bus']
        if bus_structure:
            bus_index = [i for i in block_ports if i.get_type() == 'bus'].index(self)
            ports = [p for i, p in enumerate(ports) if i in bus_structure[bus_index]]
        return ports


class PortClone(Port):

    is_clone = True

    def __init__(self, parent, direction, master, name, key):
        """
        Make a new port from nested data.

        Args:
            block: the parent element
            n: the nested odict
            dir: the direction
        """
        Element.__init__(self, parent)
        self.master = master
        self.name = name
        self._key = key
        self._nports = '1'

    def __getattr__(self, item):
        return getattr(self.master, item)

    def add_clone(self):
        raise NotImplementedError()

    def remove_clone(self, port):
        raise NotImplementedError()

