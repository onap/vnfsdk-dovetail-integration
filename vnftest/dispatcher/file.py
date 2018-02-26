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
# yardstick/dispatcher/file.py

from __future__ import absolute_import

from vnftest.dispatcher.base import Base as DispatchBase
from vnftest.common import constants as consts
from vnftest.common import utils


class FileDispatcher(DispatchBase):
    """Dispatcher class for recording data to a file.
    """

    __dispatcher_type__ = "File"

    def __init__(self, conf):
        super(FileDispatcher, self).__init__(conf)
        self.target = conf['dispatcher_file'].get('file_path',
                                                  consts.DEFAULT_OUTPUT_FILE)

    def flush_result_data(self, data):
        utils.write_json_to_file(self.target, data)
