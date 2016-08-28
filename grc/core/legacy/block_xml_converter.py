# Copyright 2016 Free Software Foundation, Inc.
# This file is part of GNU Radio
#
# GNU Radio Companion is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by the
# Free Software Foundation; either version 2 of the License, or (at your
# option) any later version.
#
# GNU Radio Companion is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or
# FITNESS FOR A PARTICULAR PURPOSE. See the GNU General Public License for more
# details.
#
# You should have received a copy of the GNU General Public License along with
# this program; if not, write to the Free Software Foundation, Inc.,
# 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA
"""
Converter for legacy block definitions in XML format

- Cheetah expressions that can not be converted are passed to Cheetah for now
- Instead of generating a Block subclass directly a string representation is
  used and evaluated. This is slower / lamer but allows us to show the user
  how a converted definition would look like
"""

from __future__ import absolute_import, division, print_function

from collections import OrderedDict

import yaml
from lxml import etree
from os import path

from .yaml_output import OrderedDictFlowing, scalar_node, GRCDumper
from . import cheetah_converter

from .. import Constants


BLOCK_DTD = etree.DTD(path.join(path.dirname(__file__), '..', 'block.dtd'))
reserved_block_keys = ('import', )  # todo: add more keys


def convert_xml(xml_file):
    """Load block description from xml file"""

    try:
        xml = etree.parse(xml_file).getroot()
        BLOCK_DTD.validate(xml)
    except etree.LxmlError:
        return

    data = convert_block_xml(xml)
    out = yaml.dump(data, default_flow_style=False, indent=4, Dumper=GRCDumper)

    replace = [
        ('params:', '\nparams:'),
        ('sinks:', '\nsinks:'),
        ('sources:', '\nsources:'),
        ('templates:', '\ntemplates:'),
        ('documentation:', '\ndocumentation:'),
    ]
    for r in replace:
        out = out.replace(*r)

    return data['key'], out

no_value = object()
dummy = cheetah_converter.DummyConverter()


def convert_block_xml(node):
    converter = cheetah_converter.Converter(names={
        param_node.findtext('key'): {
            opt_node.text.split(':')[0]
            for opt_node in next(param_node.getiterator('option'), param_node).getiterator('opt')
        } for param_node in node.getiterator('param')
    })

    key = node.findtext('key')
    if key in reserved_block_keys:
        key += '_'

    data = OrderedDict()
    data['key'] = key
    data['label'] = node.findtext('name') or no_value
    data['category'] = node.findtext('category') or no_value
    data['flags'] = node.findtext('flags') or no_value

    data['params'] = [convert_param_xml(param_node, converter.to_python_dec, key)
                      for param_node in node.getiterator('param')] or no_value
    # data['params'] = {p.pop('key'): p for p in data['params']}

    data['sinks'] = [convert_port_xml(port_node, converter.to_python_dec)
                     for port_node in node.getiterator('sink')] or no_value

    data['sources'] = [convert_port_xml(port_node, converter.to_python_dec)
                       for port_node in node.getiterator('source')] or no_value

    data['checks'] = [dummy.to_mako(check_node.text)
                      for check_node in node.getiterator('checks')] or no_value
    data['value'] = (
        node.findtext('var_value') or
        '$value' if key.startswith('variable') else None or
        no_value
    )

    data['templates'] = convert_templates(node, converter.to_mako) or no_value

    docs = node.findtext('doc')
    if docs:
        docs = docs.strip().replace('\\\n', '').replace('\n\n', '\n')
        data['documentation'] = scalar_node(docs, style='>')

    return OrderedDict((key, value) for key, value in data.items() if value is not no_value)


def convert_templates(node, convert):
    templates = OrderedDict()

    imports = [dummy.to_mako(import_node.text)
               for import_node in node.getiterator('import')]
    if imports:
        templates['imports'] = (imports if len(imports) > 1 else imports[0]) or no_value

        templates['var_make'] = dummy.to_mako(node.findtext('var_make') or '') or no_value
    make = node.findtext('make') or ''
    if '\n' in make:
        make = dummy.to_mako(make)
        templates['make'] = scalar_node(make, style='|' if '\n' in make else None)
    else:
        templates['make'] = dummy.to_mako(make) or no_value

    templates['callbacks'] = [dummy.to_mako(cb_node.text)
                              for cb_node in node.getiterator('callback')] or no_value

    return OrderedDict((key, value) for key, value in templates.items() if value is not no_value)


def convert_param_xml(node, convert, block_key=''):
    param = OrderedDict()
    key = node.findtext('key').strip()
    param['label'] = node.findtext('name').strip()
    param['category'] = node.findtext('tab') or no_value

    param['dtype'] = convert(node.findtext('type') or '')
    param['default'] = node.findtext('value') or no_value

    options = []
    for option_n in node.getiterator('option'):
        option = OrderedDict()
        option['name'] = option_n.findtext('name')
        option['value'] = option_n.findtext('key')

        opts = (opt.text for opt in option_n.getiterator('opt'))
        attributes = OrderedDictFlowing(
            opt_n.split(':', 2) for opt_n in opts if ':' in opt_n
        )
        if attributes:
            option['attributes'] = attributes
        options.append(option)

    param['options'] = options or no_value

    param['hide'] = hide = convert(node.findtext('hide')) or no_value
    if hide is not no_value:
        print(block_key, hide)

    return {key: OrderedDict((key, value) for key, value in param.items() if value is not no_value)}


def convert_port_xml(node, convert):
    port = OrderedDict()
    port['label'] = node.findtext('name')

    dtype = convert(node.findtext('type'))
    # TODO: detect dyn message ports
    # todo: parse hide, tab tags
    port['domain'] = domain = Constants.GR_MESSAGE_DOMAIN if dtype == 'message' else Constants.DEFAULT_DOMAIN
    if domain == Constants.GR_MESSAGE_DOMAIN:
        port['key'] = port['label']
    else:
        port['dtype'] = dtype
        vlen = node.findtext('vlen')
        port['vlen'] = int(vlen) if vlen and vlen.isdigit() else convert(vlen) or no_value

    port['multiplicity'] = convert(node.findtext('nports')) or no_value
    port['optional'] = bool(node.findtext('optional')) or no_value
    port['hide'] = convert(node.findtext('hide')) or no_value

    return OrderedDict((key, value) for key, value in port.items() if value is not no_value)
