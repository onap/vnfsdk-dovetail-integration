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
# yardstick/benchmark/core/task.py

""" Handler for vnftest command 'task' """

from __future__ import absolute_import
from __future__ import print_function

import atexit
import collections
import copy
import logging
import sys
import time
import traceback
import uuid

import ipaddress
import os
import yaml
from jinja2 import Environment
from six.moves import filter

from vnftest.runners import base as base_runner

from vnftest.contexts.base import Context
from vnftest.runners import base as base_runner
from vnftest.runners.duration import DurationRunner
from vnftest.runners.iteration import IterationRunner
from vnftest.common.constants import CONF_FILE
from vnftest.common.html_template import report_template
from vnftest.common.task_template import TaskTemplate
from vnftest.common.yaml_loader import yaml_load
from vnftest.contexts.base import Context
from vnftest.dispatcher.base import Base as DispatcherBase
from vnftest.common.task_template import TaskTemplate
from vnftest.common import utils
from vnftest.common import constants
from vnftest.common.html_template import report_template

output_file_default = "/tmp/vnftest.out"
LOG = logging.getLogger(__name__)


class Task(object):     # pragma: no cover
    """Task commands.

       Set of commands to manage benchmark tasks.
    """

    def __init__(self, args):
        self.contexts = None
        self.outputs = {}
        self.args = args or {}
        task_id = getattr(args, 'task_id', None)
        self.task_id = task_id if task_id is not None else str(uuid.uuid4())
        self.task_info = TaskInfo(task_id)

    def _set_dispatchers(self, output_config):
        dispatchers = output_config.get('DEFAULT', {}).get('dispatcher',
                                                           'file')
        out_types = [s.strip() for s in dispatchers.split(',')]
        output_config['DEFAULT']['dispatcher'] = out_types

    def start(self):
        atexit.register(self.atexit_handler)
        self._set_log()
        try:
            output_config = utils.parse_ini_file(CONF_FILE)
        except Exception:
            # all error will be ignore, the default value is {}
            output_config = {}

        self._init_output_config(output_config)
        self._set_output_config(output_config, self.args.output_file)
        LOG.debug('Output configuration is: %s', output_config)

        self._set_dispatchers(output_config)

        # update dispatcher list
        if 'file' in output_config['DEFAULT']['dispatcher']:
            result = {'status': 0, 'result': {}}
            utils.write_json_to_file(self.args.output_file, result)

        total_start_time = time.time()
        parser = TaskParser(self.args.inputfile)

        if self.args.suite:
            # 1.parse suite, return suite_params info
            task_files, task_args_list, task_args_fnames = parser.parse_suite()

        else:
            task_files = [parser.path]
            task_args_list = [{}]
            task_args_fnames = [self.args.task_args_file]

        LOG.debug("task_files:%s, task_args_list:%s, task_args_fnames:%s",
                  task_files, task_args_list, task_args_fnames)

        if self.args.parse_only:
            sys.exit(0)

        try:
            for i in range(0, len(task_files)):
                one_task_start_time = time.time()
                # the output of the previous task is the input of the new task
                inputs = copy.deepcopy(self.outputs)
                task_args_file = task_args_fnames[i]
                task_args = task_args_list[i]
                try:
                    inputs.update(parse_task_args("global_task_args", self.args.task_args))
                    if task_args_file:
                        with utils.load_resource(task_args_file) as f:
                            inputs.update(parse_task_args("task_args_file", f.read()))
                    # task args from suite may override file args.
                    inputs.update(parse_task_args("task_args", task_args))
                except TypeError:
                    raise TypeError()
                parser.path = task_files[i]
                steps, run_in_parallel, meet_precondition, ret_contexts = \
                    parser.parse_task(self.task_id, inputs)

                self.contexts = ret_contexts

                if not meet_precondition:
                    LOG.info("meet_precondition is %s, please check envrionment",
                             meet_precondition)
                    continue

                case_name = os.path.splitext(os.path.basename(task_files[i]))[0]
                try:
                    self._run(steps, case_name, run_in_parallel, self.args.output_file, inputs)
                except KeyboardInterrupt:
                    raise
                except Exception:
                    LOG.error('Testcase: "%s" FAILED!!!', case_name, exc_info=True)

                if self.args.keep_deploy:
                    # keep deployment, forget about stack
                    # (hide it for exit handler)
                    self.contexts = None
                else:
                    if self.contexts is not None:
                        for context in self.contexts:
                            context.undeploy()
                        self.contexts = None
                one_task_end_time = time.time()
                LOG.info("Task %s finished in %d secs", task_files[i],
                         one_task_end_time - one_task_start_time)
        except Exception as e:
            LOG.error("Task fatal error: %s", e)
            traceback.print_exc()
            self.task_info.task_fatal()
        finally:
            self.task_info.task_end()

        self._do_output(output_config)
        self._generate_reporting()

        total_end_time = time.time()
        LOG.info("Total finished in %d secs",
                 total_end_time - total_start_time)
        return self.task_info.result()

    def _generate_reporting(self):
        env = Environment()
        file_name = 'report_' + str(self.task_id) + '.html'
        report_file = os.path.join(constants.REPORT_DIR, file_name)
        with open(report_file, 'w') as f:
            f.write(env.from_string(report_template).render(self.task_info.result()))

        LOG.info("Report can be found in '%s'", report_file)

    def _set_log(self):
        log_format = '%(asctime)s %(name)s %(filename)s:%(lineno)d %(levelname)s %(message)s'
        log_formatter = logging.Formatter(log_format)

        utils.makedirs(constants.TASK_LOG_DIR)
        log_path = os.path.join(constants.TASK_LOG_DIR, '{}.log'.format(self.task_id))
        log_handler = logging.FileHandler(log_path)
        log_handler.setFormatter(log_formatter)
        log_handler.setLevel(logging.DEBUG)

        logging.root.addHandler(log_handler)

    def _init_output_config(self, output_config):
        output_config.setdefault('DEFAULT', {})
        output_config.setdefault('dispatcher_http', {})
        output_config.setdefault('dispatcher_file', {})
        output_config.setdefault('dispatcher_influxdb', {})

    def _set_output_config(self, output_config, file_path):
        try:
            out_type = os.environ['DISPATCHER']
        except KeyError:
            output_config['DEFAULT'].setdefault('dispatcher', 'file')
        else:
            output_config['DEFAULT']['dispatcher'] = out_type

        output_config['dispatcher_file']['file_path'] = file_path

        try:
            target = os.environ['TARGET']
        except KeyError:
            pass
        else:
            k = 'dispatcher_{}'.format(output_config['DEFAULT']['dispatcher'])
            output_config[k]['target'] = target

    def _do_output(self, output_config):
        dispatchers = DispatcherBase.get(output_config)

        for dispatcher in dispatchers:
            dispatcher.flush_result_data(self.task_id, self.task_info.result())

    def _run(self, steps, case_name, run_in_parallel, output_file, inputs):
        try:
            self.task_info.testcase_start(case_name)
            for step in steps:
                step_unique_id = self.task_info.step_add(case_name, step['name'])
                step['step_unique_id'] = step_unique_id

            """Deploys context and calls runners"""
            if self.contexts is not None:
                for context in self.contexts:
                    output = None
                    try:
                        self.task_info.context_deploy_start(case_name, context.assigned_name)
                        output = context.deploy()
                    finally:
                        self.task_info.context_deploy_end(case_name, context.assigned_name, output)

            background_runners = []
            result = []
            # Start all background steps
            for step in filter(_is_background_step, steps):
                step["runner"] = dict(type="Duration", duration=1000000000)
                self.task_info.step_start(step['step_unique_id'])
                runner = self.run_one_step(step, output_file, inputs)
                background_runners.append([step, runner])

            runners = []
            if run_in_parallel:
                for step in steps:
                    if not _is_background_step(step):
                        self.task_info.step_start(step['step_unique_id'])
                        runner = self.run_one_step(step, output_file, inputs)
                        runners.append([step, runner])

                # Wait for runners to finish
                for runner_item in runners:
                    self.finalize_step(runner_item[0], runner_item[1], result)
            else:
                # run serially
                for step in steps:
                    if not _is_background_step(step):
                        self.task_info.step_start(step['step_unique_id'])
                        runner = self.run_one_step(step, output_file, inputs)
                        self.finalize_step(step, runner, result)

            # Abort background runners
            for runner_item in background_runners:
                runner_item[1].abort()

            # Wait for background runners to finish
            for runner_item in background_runners:
                runner = runner_item[1]
                self.finalize_step(step, runner, result)
            return result
        except Exception as e:
            LOG.exception('Case fatal error: %s', e)
            traceback.print_exc()
            self.task_info.testcase_fatal(case_name)
        finally:
            self.task_info.testcase_end(case_name)

    def atexit_handler(self):
        """handler for process termination"""
        base_runner.Runner.terminate_all()

        if self.contexts:
            LOG.info("Undeploying context")
            for context in self.contexts:
                context.undeploy()

    def _parse_options(self, op):
        if isinstance(op, dict):
            return {k: self._parse_options(v) for k, v in op.items()}
        elif isinstance(op, list):
            return [self._parse_options(v) for v in op]
        elif isinstance(op, str):
            return self.outputs.get(op[1:]) if op.startswith('$') else op
        else:
            return op

    def run_one_step(self, step_cfg, output_file, inputs):
        """run one step using context"""
        # default runner is Iteration
        if 'runner' not in step_cfg:
            step_cfg['runner'] = dict(type="Iteration", iterations=1)
        runner_cfg = step_cfg['runner']
        runner_cfg['output_filename'] = output_file
        options = step_cfg.get('options', {})
        step_cfg['options'] = self._parse_options(options)
        runner = base_runner.Runner.get(runner_cfg)

        LOG.info("Starting runner of type '%s'", runner_cfg["type"])
        # Previous steps output is the input of the next step.
        inputs.update(self.outputs)
        _resolve_step_options(step_cfg, self.contexts, inputs)
        runner.run(step_cfg, self.contexts, inputs)
        return runner

    def finalize_step(self, step, runner, result):
        step_result_list = []
        status = runner_join(runner, self.outputs, step_result_list)
        self.task_info.step_end(step['step_unique_id'], step_result_list)
        if status != 0:
            raise RuntimeError(
                "{0} runner status {1}".format(runner.__execution_type__, status))
        LOG.info("Runner ended")
        result.extend(step_result_list)


def _resolve_step_options(step_cfg, contexts, inputs):
    inputs = copy.deepcopy(inputs)
    contexts_dict = {}
    inputs['context'] = contexts_dict
    if contexts is not None:
        for context in contexts:
            context_as_dict = utils.normalize_data_struct(context)
            contexts_dict[context.assigned_name] = context_as_dict
    options = step_cfg.get("options", {})
    resolved_options = {}
    for k, v in options.items():
        v = utils.format(v, inputs)
        resolved_options[k] = v
    step_cfg["options"] = resolved_options


class TaskParser(object):       # pragma: no cover
    """Parser for task config files in yaml format"""

    def __init__(self, path):
        self.path = path

    def _meet_constraint(self, task, cur_pod, cur_installer):
        if "constraint" in task:
            constraint = task.get('constraint', None)
            if constraint is not None:
                tc_fit_pod = constraint.get('pod', None)
                tc_fit_installer = constraint.get('installer', None)
                LOG.info("cur_pod:%s, cur_installer:%s,tc_constraints:%s",
                         cur_pod, cur_installer, constraint)
                if (cur_pod is None) or (tc_fit_pod and cur_pod not in tc_fit_pod):
                    return False
                if (cur_installer is None) or (tc_fit_installer and cur_installer
                                               not in tc_fit_installer):
                    return False
        return True

    def _get_task_para(self, task, cur_pod):
        task_args = task.get('task_args', None)
        if task_args is not None:
            task_args = task_args.get(cur_pod, task_args.get('default'))
        task_args_fnames = task.get('task_args_fnames', None)
        if task_args_fnames is not None:
            task_args_fnames = task_args_fnames.get(cur_pod, None)
        return task_args, task_args_fnames

    def parse_suite(self):
        """parse the suite file and return a list of task config file paths
           and lists of optional parameters if present"""
        LOG.info("\nParsing suite file:%s", self.path)

        try:
            with utils.load_resource(self.path) as stream:
                cfg = yaml_load(stream)
        except IOError as ioerror:
            LOG.error("Open suite file failed", ioerror)
            raise

        self._check_schema(cfg["schema"], "suite")
        LOG.info("\nStarting step:%s", cfg["name"])

        cur_pod = os.environ.get('NODE_NAME', "default")
        cur_installer = os.environ.get('INSTALLER_TYPE', None)

        valid_task_files = []
        valid_task_args = []
        valid_task_args_fnames = []

        for task in cfg["test_cases"]:
            # 1.check file_name
            if "file_name" in task:
                task_fname = task.get('file_name', None)
                if task_fname is None:
                    continue
            else:
                continue
            # 2.check constraint
            if self._meet_constraint(task, cur_pod, cur_installer):
                valid_task_files.append(task_fname)
            else:
                continue
            # 3.fetch task parameters
            task_args, task_args_fnames = self._get_task_para(task, cur_pod)
            valid_task_args.append(task_args)
            valid_task_args_fnames.append(task_args_fnames)

        return valid_task_files, valid_task_args, valid_task_args_fnames

    def parse_task(self, task_id, inputs=None):
        """parses the task file and return an context and step instances"""
        LOG.info("Parsing task config: %s", self.path)
        kw = inputs
        try:
            with utils.load_resource(self.path) as f:
                try:
                    input_task = f.read()
                    rendered_task = TaskTemplate.render(input_task, **kw)
                except Exception as e:
                    LOG.exception('Failed to render template:\n%s\n', input_task)
                    raise e
                LOG.debug("Input task is:\n%s\n", rendered_task)

                cfg = yaml_load(rendered_task)
        except IOError as ioerror:
            sys.exit(ioerror)

        self._check_schema(cfg["schema"], "task")
        meet_precondition = self._check_precondition(cfg)

        if "context" in cfg:
            context_cfgs = [cfg["context"]]
        elif "contexts" in cfg:
            context_cfgs = cfg["contexts"]
        else:
            context_cfgs = [{"type": "Dummy", "name": "Dummy"}]

        _contexts = []
        for cfg_attrs in context_cfgs:
            cfg_attrs['task_id'] = task_id
            context_type = cfg_attrs.get("type")
            context = Context.get(context_type)
            context.init(cfg_attrs)
            _contexts.append(context)

        run_in_parallel = cfg.get("run_in_parallel", False)

        # add tc and task id for influxdb extended tags
        for step in cfg["steps"]:
            task_name = os.path.splitext(os.path.basename(self.path))[0]
            step["tc"] = task_name
            step["task_id"] = task_id
            # embed task path into step so we can load other files
            # relative to task path
            step["task_path"] = os.path.dirname(self.path)

        # TODO we need something better here, a class that represent the file
        return cfg["steps"], run_in_parallel, meet_precondition, _contexts

    def _check_schema(self, cfg_schema, schema_type):
        """Check if config file is using the correct schema type"""

        if cfg_schema != "vnftest:" + schema_type + ":0.1":
            sys.exit("error: file %s has unknown schema %s" % (self.path,
                                                               cfg_schema))

    def _check_precondition(self, cfg):
        """Check if the environment meet the precondition"""

        if "precondition" in cfg:
            precondition = cfg["precondition"]
            installer_type = precondition.get("installer_type", None)
            tc_fit_pods = precondition.get("pod_name", None)
            installer_type_env = os.environ.get('INSTALL_TYPE', None)
            pod_name_env = os.environ.get('NODE_NAME', None)

            LOG.info("installer_type: %s, installer_type_env: %s",
                     installer_type, installer_type_env)
            LOG.info("tc_fit_pods: %s, pod_name_env: %s",
                     tc_fit_pods, pod_name_env)
            if installer_type and installer_type_env:
                if installer_type_env not in installer_type:
                    return False
                return False
            if tc_fit_pods and pod_name_env:
                if pod_name_env not in tc_fit_pods:
                    return False
        return True


class TaskInfo(object):

    def __init__(self, task_id):
        self.info_dict = {'task_id': task_id, 'status': 'IN_PROGRESS', 'criteria': 'N/A'}
        self.result_info_dict = {}
        self.info_dict['info'] = self.result_info_dict
        self.test_cases_list = []
        self.info_dict['testcases'] = self.test_cases_list
        self.helper_test_cases_dict = {}
        self.helper_test_steps_dict = {}
        self.helper_contexts_dict = {}
        self.step_id_helper = 0

    def task_end(self):
        if self.info_dict['criteria'] == 'N/A':
            criteria = 'PASS'
            for testcase in self.info_dict['testcases']:
                if testcase['criteria'] == 'FAIL' or testcase['criteria'] == 'FATAL':
                    criteria = 'FAIL'
                    break
            self.info_dict['criteria'] = criteria
            self.info_dict['status'] = 'FINISHED'

    def task_fatal(self):
        self.info_dict['criteria'] = 'FATAL'
        self.info_dict['status'] = 'FINISHED'

    def testcase_fatal(self, testcase_name):
        testcase_dict = self.helper_test_cases_dict[testcase_name]
        testcase_dict['criteria'] = 'FATAL'
        testcase_dict['status'] = 'FINISHED'

    def testcase_start(self, testcase_name):
        testcase_dict = {'name': testcase_name, 'criteria': 'N/A', 'status': 'IN_PROGRESS', 'steps': [], 'contexts': []}
        self.test_cases_list.append(testcase_dict)
        self.helper_test_cases_dict[testcase_name] = testcase_dict

    def testcase_end(self, testcase_name):
        testcase_dict = self.helper_test_cases_dict[testcase_name]
        if testcase_dict['criteria'] == 'N/A':
            criteria = 'PASS'
            for step in testcase_dict['steps']:
                if step['criteria'] == 'FAIL':
                    criteria = 'FAIL'
                    break
            testcase_dict['criteria'] = criteria
            testcase_dict['status'] = 'FINISHED'

    def step_add(self, testcase_name, step_name):
        step_dict = {'name': step_name, 'criteria': 'N/A', 'status': 'NOT_STARTED', 'results': []}
        testcase_dict = self.helper_test_cases_dict[testcase_name]
        testcase_dict['steps'].append(step_dict)
        self.step_id_helper += 1
        step_unique_id = step_name + '_' + str(self.step_id_helper)
        self.helper_test_steps_dict[step_unique_id] = step_dict
        return step_unique_id

    def step_start(self, step_unique_id):
        step_dict = self.helper_test_steps_dict[step_unique_id]
        step_dict['status'] = 'IN_PROGRESS'

    def step_end(self, step_unique_id, result_list):
        step_dict = self.helper_test_steps_dict[step_unique_id]
        errors_count = 0
        for result in result_list:
            result_item = {
                'timestamp': result['timestamp'],
                'sequence': result['sequence'],
                'data': [],
                'errors': []
            }
            for k, v in result['data'].items():
                result_item['data'].append({'type': 'String', 'key': k, 'value': str(v)})

            for error in result['errors']:
                result_item['errors'].append({'type': 'String', 'key': 'error', 'value': str(error)})
                errors_count += 1
            step_dict['results'].append(result_item)
        if errors_count > 0:
            step_dict['criteria'] = 'FAIL'
        else:
            step_dict['criteria'] = 'PASS'
        step_dict['status'] = 'FINISHED'

    def context_deploy_start(self, testcase_name, context_name):
        context_dict = {'name': context_name, 'status': 'IN_PROGRESS', 'output': []}
        testcase_dict = self.helper_test_cases_dict[testcase_name]
        testcase_dict['contexts'].append(context_dict)
        context_unique_id = testcase_name + '_' + context_name
        self.helper_contexts_dict[context_unique_id] = context_dict

    def context_deploy_end(self, testcase_name, context_name, output):
        context_unique_id = testcase_name + '_' + context_name
        context_dict = self.helper_contexts_dict[context_unique_id]
        if output is not None:
            for k, v in output.items():
                context_dict['output'].append({'type': 'String', 'key': k, 'value': str(v)})
        context_dict['status'] = 'FINISHED'

    def result(self):
        return copy.deepcopy(self.info_dict)


def is_ip_addr(addr):
    """check if string addr is an IP address"""
    try:
        addr = addr.get('public_ip_attr', addr.get('private_ip_attr'))
    except AttributeError:
        pass

    try:
        ipaddress.ip_address(addr.encode('utf-8'))
    except ValueError:
        return False
    else:
        return True


def _is_background_step(step):
    if "run_in_background" in step:
        return step["run_in_background"]
    else:
        return False


def runner_join(runner, outputs, result):
    while runner.poll() is None:
        outputs.update(runner.get_output())
        result.extend(runner.get_result())
    status = runner.join(outputs, result)
    base_runner.Runner.release(runner)
    return status


def print_invalid_header(source_name, args):
    print("Invalid %(source)s passed:\n\n %(args)s\n"
          % {"source": source_name, "args": args})


def parse_task_args(src_name, args):
    if isinstance(args, collections.Mapping):
        return args

    try:
        kw = args and yaml_load(args)
        kw = {} if kw is None else kw
    except yaml.parser.ParserError as e:
        print_invalid_header(src_name, args)
        print("%(source)s has to be YAML. Details:\n\n%(err)s\n"
              % {"source": src_name, "err": e})
        raise TypeError()

    if not isinstance(kw, dict):
        print_invalid_header(src_name, args)
        print("%(src)s had to be dict, actually %(src_type)s\n"
              % {"src": src_name, "src_type": type(kw)})
        raise TypeError()
    return kw