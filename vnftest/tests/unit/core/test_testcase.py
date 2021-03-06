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
# yardstick/tests/unit/benchmark/core/test_testcase.py

from __future__ import absolute_import
import unittest

from vnftest.core import testcase


class Arg(object):

    def __init__(self):
        self.casename = ('onap_vnftest_onboard-v1',)


class TestcaseUT(unittest.TestCase):

    def test_list_all(self):
        t = testcase.Testcase()
        result = t.list_all("")
        self.assertIsInstance(result, list)

    def test_show(self):
        t = testcase.Testcase()
        casename = Arg()
        result = t.show(casename)
        self.assertTrue(result)
