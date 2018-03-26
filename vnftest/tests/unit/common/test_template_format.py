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
# yardstick/tests/unit/common/test_template_format.py

from __future__ import absolute_import
import mock
import unittest
import yaml

from vnftest.common import template_format


class TemplateFormatTestCase(unittest.TestCase):

    def test_parse_to_value_exception(self):

        # TODO(elfoley): Don't hide the error that occurs in
        # template_format.parse
        # TODO(elfoley): Separate these tests; one per error type
        with mock.patch.object(yaml, 'load') as yaml_loader:
            yaml_loader.side_effect = yaml.scanner.ScannerError()
            self.assertRaises(ValueError, template_format.parse, 'FOOBAR')
            yaml_loader.side_effect = yaml.parser.ParserError()
            self.assertRaises(ValueError, template_format.parse, 'FOOBAR')
            yaml_loader.side_effect = \
                yaml.reader.ReaderError('', '', '', '', '')
            self.assertRaises(ValueError, template_format.parse, 'FOOBAR')

    def test_parse_no_version_format(self):

        yaml = ''
        self.assertRaises(ValueError, template_format.parse, yaml)
        yaml2 = "Parameters: {}\n" \
                "Mappings: {}\n" \
                "Resources: {}\n" \
                "Outputs: {}"
        self.assertRaises(ValueError, template_format.parse, yaml2)
