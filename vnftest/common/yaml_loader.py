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
# yardstick/common/yaml_loader.py

from __future__ import absolute_import

import yaml


if hasattr(yaml, 'CSafeLoader'):
    # make a dynamic subclass so we don't override global yaml Loader
    yaml_loader = type('CustomLoader', (yaml.CSafeLoader,), {})
else:
    yaml_loader = type('CustomLoader', (yaml.SafeLoader,), {})

if hasattr(yaml, 'CSafeDumper'):
    yaml_dumper = yaml.CSafeDumper
else:
    yaml_dumper = yaml.SafeDumper


def yaml_load(tmpl_str):
    return yaml.load(tmpl_str, Loader=yaml_loader)
