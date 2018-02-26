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
# rally/rally/benchmark/runners/search.py

"""A runner that runs a specific time before it returns
"""

from __future__ import absolute_import

import logging
import multiprocessing
import time
import traceback
from contextlib import contextmanager
from itertools import takewhile

import os
from collections import Mapping
from six.moves import zip

from vnftest.onap.runners import base

LOG = logging.getLogger(__name__)


class SearchRunnerHelper(object):

    def __init__(self, cls, method_name, step_cfg, context_cfg, aborted):
        super(SearchRunnerHelper, self).__init__()
        self.cls = cls
        self.method_name = method_name
        self.step_cfg = step_cfg
        self.context_cfg = context_cfg
        self.aborted = aborted
        self.runner_cfg = step_cfg['runner']
        self.run_step = self.runner_cfg.get("run_step", "setup,run,teardown")
        self.timeout = self.runner_cfg.get("timeout", 60)
        self.interval = self.runner_cfg.get("interval", 1)
        self.step = None
        self.method = None

    def __call__(self, *args, **kwargs):
        if self.method is None:
            raise RuntimeError
        return self.method(*args, **kwargs)

    @contextmanager
    def get_step_instance(self):
        self.step = self.cls(self.step_cfg, self.context_cfg)

        if 'setup' in self.run_step:
            self.step.setup()

        self.method = getattr(self.step, self.method_name)
        LOG.info("worker START, timeout %d sec, class %s", self.timeout, self.cls)
        try:
            yield self
        finally:
            if 'teardown' in self.run_step:
                self.step.teardown()

    def is_not_done(self):
        if 'run' not in self.run_step:
            raise StopIteration

        max_time = time.time() + self.timeout

        abort_iter = iter(self.aborted.is_set, True)
        time_iter = takewhile(lambda t_now: t_now <= max_time, iter(time.time, -1))

        for seq, _ in enumerate(zip(abort_iter, time_iter), 1):
            yield seq
            time.sleep(self.interval)


class SearchRunner(base.Runner):
    """Run a step for a certain amount of time

If the step ends before the time has elapsed, it will be started again.

  Parameters
    timeout - amount of time the step will be run for
        type:    int
        unit:    seconds
        default: 1 sec
    interval - time to wait between each step invocation
        type:    int
        unit:    seconds
        default: 1 sec
    """
    __execution_type__ = 'Search'

    def __init__(self, config):
        super(SearchRunner, self).__init__(config)
        self.runner_cfg = None
        self.runner_id = None
        self.sla_action = None
        self.worker_helper = None

    def _worker_run_once(self, sequence):
        LOG.debug("runner=%s seq=%s START", self.runner_id, sequence)

        data = {}
        errors = ""

        try:
            self.worker_helper(data)
        except AssertionError as assertion:
            # SLA validation failed in step, determine what to do now
            if self.sla_action == "assert":
                raise
            elif self.sla_action == "monitor":
                LOG.warning("SLA validation failed: %s", assertion.args)
                errors = assertion.args
        except Exception as e:
            errors = traceback.format_exc()
            LOG.exception(e)

        record = {
            'runner_id': self.runner_id,
            'step': {
                'timestamp': time.time(),
                'sequence': sequence,
                'data': data,
                'errors': errors,
            },
        }

        self.result_queue.put(record)

        LOG.debug("runner=%s seq=%s END", self.runner_id, sequence)

        # Have to search through all the VNF KPIs
        kpi_done = any(kpi.get('done') for kpi in data.values() if isinstance(kpi, Mapping))

        return kpi_done or (errors and self.sla_action is None)

    def _worker_run(self, cls, method_name, step_cfg, context_cfg):
        self.runner_cfg = step_cfg['runner']
        self.runner_id = self.runner_cfg['runner_id'] = os.getpid()

        self.worker_helper = SearchRunnerHelper(cls, method_name, step_cfg,
                                                context_cfg, self.aborted)

        try:
            self.sla_action = step_cfg['sla'].get('action', 'assert')
        except KeyError:
            self.sla_action = None

        self.result_queue.put({
            'runner_id': self.runner_id,
            'step_cfg': step_cfg,
            'context_cfg': context_cfg
        })

        with self.worker_helper.get_step_instance():
            for sequence in self.worker_helper.is_not_done():
                if self._worker_run_once(sequence):
                    LOG.info("worker END")
                    break

    def _run_step(self, cls, method, step_cfg, context_cfg):
        name = "{}-{}-{}".format(self.__execution_type__, step_cfg.get("type"), os.getpid())
        self.process = multiprocessing.Process(
            name=name,
            target=self._worker_run,
            args=(cls, method, step_cfg, context_cfg))
        self.process.start()
