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
# yardstick/cmd/commands/env.py
from __future__ import absolute_import
from __future__ import print_function

import os
import sys
import time

from six.moves import range

from vnftest.common import constants as consts
from vnftest.common.httpClient import HttpClient


class EnvCommand(object):
    """

        Set of commands to prepare environment
    """

    def do_influxdb(self, args):
        data = {'action': 'create_influxdb'}
        task_id = self._start_async_task(data)

        start = '* creating influxDB'
        self._check_status(task_id, start)

    def do_grafana(self, args):
        data = {'action': 'create_grafana'}
        task_id = self._start_async_task(data)

        start = '* creating grafana'
        self._check_status(task_id, start)

    def do_prepare(self, args):
        data = {'action': 'prepare_env'}
        task_id = self._start_async_task(data)

        start = '* preparing vnftest environment'
        self._check_status(task_id, start)

    def _start_async_task(self, data):
        url = consts.ENV_ACTION_API
        return HttpClient().post(url, data)['result']['task_id']

    def _check_status(self, task_id, start):
        self._print_status(start, '[]\r')
        url = '{}?task_id={}'.format(consts.ASYNC_TASK_API, task_id)

        CHECK_STATUS_RETRY = 20
        CHECK_STATUS_DELAY = 5

        for retry in range(CHECK_STATUS_RETRY):
            response = HttpClient().get(url)
            status = response['status']

            if status:
                break

            # wait until the async task finished
            time.sleep(CHECK_STATUS_DELAY * (retry + 1))

        switcher = {
            0: 'Timeout',
            1: 'Finished',
            2: 'Error'
        }
        self._print_status(start, '[{}]'.format(switcher[status]))
        if status == 2:
            print(response['result'])
            sys.stdout.flush()
        return status

    def _print_status(self, s, e):
        try:
            columns = int(os.popen('stty size', 'r').read().split()[1])
            word = '{}{}{}'.format(s, ' ' * (columns - len(s) - len(e)), e)
            sys.stdout.write(word)
            sys.stdout.flush()
        except IndexError:
            pass
