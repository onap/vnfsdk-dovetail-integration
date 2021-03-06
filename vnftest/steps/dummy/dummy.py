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
from __future__ import absolute_import

import logging

from vnftest.steps import base

LOG = logging.getLogger(__name__)


class Dummy(base.Step):
    """Execute Dummy echo
    """
    __step_type__ = "Dummy"

    def __init__(self, step_cfg, context_cfg):
        self.step_cfg = step_cfg
        self.context_cfg = context_cfg
        self.setup_done = False

    def setup(self):
        """step setup"""
        self.setup_done = True

    def run(self, result):
        if not self.setup_done:
            self.setup()

        result["hello"] = "vnftest"
        LOG.info("Dummy echo hello vnftest!")
