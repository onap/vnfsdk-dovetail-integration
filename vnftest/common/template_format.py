##############################################################################
# Copyright 2018 EuropeanSoftwareMarketingLtd.
# ===================================================================
#  Licensed under the ApacheLicense, Version2.0 (the"License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#  http://www.apache.org/licenses/LICENSE-2.0
#
# software distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and limitations under
# the License
##############################################################################
# vnftest comment: this is a modified copy of
# yardstick/common/template_format.py

from __future__ import absolute_import

import yaml
from oslo_serialization import jsonutils

if hasattr(yaml, 'CSafeLoader'):
    # make a dynamic subclass so we don't override global yaml Loader
    yaml_loader = type('HeatYamlLoader', (yaml.CSafeLoader,), {})
else:
    yaml_loader = type('HeatYamlLoader', (yaml.SafeLoader,), {})

if hasattr(yaml, 'CSafeDumper'):
    yaml_dumper = yaml.CSafeDumper
else:
    yaml_dumper = yaml.SafeDumper


# This breaks NetworkServiceTestCase yaml loading, because we need to conversion to
# native Python str() objects because we use use Trex and Trex is has broken unicode handling
def _construct_yaml_str(self, node):
    # Override the default string handling function
    # to always return unicode objects
    return self.construct_scalar(node)

yaml_loader.add_constructor(u'tag:yaml.org,2002:str', _construct_yaml_str)
# Unquoted dates like 2013-05-23 in yaml files get loaded as objects of type
# datetime.data which causes problems in API layer when being processed by
# openstack.common.jsonutils. Therefore, make unicode string out of timestamps
# until jsonutils can handle dates.
yaml_loader.add_constructor(u'tag:yaml.org,2002:timestamp',
                            _construct_yaml_str)


def parse(tmpl_str):
    """Takes a string and returns a dict containing the parsed structure.

    This includes determination of whether the string is using the
    JSON or YAML format.
    """
    if tmpl_str.startswith('{'):
        tpl = jsonutils.loads(tmpl_str)
    else:
        try:
            # we already use SafeLoader when constructing special Heat YAML loader class
            tpl = yaml.load(tmpl_str, Loader=yaml_loader)
        except yaml.YAMLError as yea:
            raise ValueError(yea)
        else:
            if tpl is None:
                tpl = {}
    # Looking for supported version keys in the loaded template
    if not ('HeatTemplateFormatVersion' in tpl or
            'heat_template_version' in tpl or
            'AWSTemplateFormatVersion' in tpl):
        raise ValueError("Template format version not found.")
    return tpl
