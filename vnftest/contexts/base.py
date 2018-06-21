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
import abc
import six
from vnftest.common import openstack_utils

import vnftest.common.utils as utils
import yaml


@six.add_metaclass(abc.ABCMeta)
class Context(object):
    """Class that represents a context in the logical model"""
    list = []
    vnf_descriptor = {}
    creds = {}

    @classmethod
    def initialize(cls, vnf_descriptor_path):
        with open(vnf_descriptor_path) as f:
            cls.vnf_descriptor = yaml.safe_load(f)
        for key, value in openstack_utils.get_credentials().iteritems():
            cls.creds[key] = value

    @staticmethod
    def split_name(name, sep='.'):
        try:
            name_iter = iter(name.split(sep))
        except AttributeError:
            # name is not a string
            return None, None
        return next(name_iter), next(name_iter, None)

    def __init__(self):
        Context.list.append(self)

    def init(self, attrs):
        pass

    @staticmethod
    def get_cls(context_type):
        """Return class of specified type."""
        for context in utils.findsubclasses(Context):
            if context_type == context.__context_type__:
                return context
        raise RuntimeError("No such context_type %s" % context_type)

    @staticmethod
    def get(context_type):
        """Returns instance of a context for context type.
        """
        return Context.get_cls(context_type)()

    def _delete_context(self):
        Context.list.remove(self)

    @abc.abstractmethod
    def deploy(self):
        """Deploy context."""

    @abc.abstractmethod
    def undeploy(self):
        """Undeploy context."""
        self._delete_context()