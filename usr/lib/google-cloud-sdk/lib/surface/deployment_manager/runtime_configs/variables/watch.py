# Copyright 2016 Google Inc. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""The runtime-configs variables watch command."""

import socket

from apitools.base.py import exceptions as apitools_exceptions

from googlecloudsdk.api_lib.deployment_manager.runtime_configs import util
from googlecloudsdk.calliope import arg_parsers
from googlecloudsdk.calliope import base
from googlecloudsdk.calliope import exceptions as base_exceptions
from googlecloudsdk.command_lib.deployment_manager.runtime_configs import flags
from googlecloudsdk.core.console import progress_tracker
from googlecloudsdk.core.util import times


TIMEOUT_MESSAGE = 'The read operation timed out'


class Watch(base.Command):
  """Wait for a variable resources to change.

  This command waits for the variable resource with the specified name to either
  have its value changed or be deleted.
  """

  detailed_help = {
      'DESCRIPTION': '{description}',
      'EXAMPLES': """\
          To wait for a variable to change or be deleted, run:

            $ {command} my-var --config-name my-config

          This command will return after the variable changes,
          is deleted, or a server-defined timeout elapses.

          To wait for user-specified period of 20 seconds, run:

            $ {command} my-var --config-name my-config --max-wait 20

          If a watch command returns due to a timeout, the command's exit value
          will be 2. All other errors result in an exit value of 1. If the
          watched variable changes prior to the timeout, the command will exit
          successfully with a value of 0.

          Optionally, a --newer-than parameter can be specified to wait only
          if the variable hasn't changed since the specified time. If the
          variable has changed since the time passed to --newer-than, the
          command returns without waiting. For example:

            $ {command} my-var --config-name my-config --newer-than "2016-04-05T12:00:00Z"
          """,
  }

  @staticmethod
  def Args(parser):
    """Args is called by calliope to gather arguments for this command.

    Args:
      parser: An argparse parser that you can use to add arguments that go
          on the command line after this command. Positional arguments are
          allowed.
    """
    flags.AddConfigFlag(parser)

    parser.add_argument('--newer-than',
                        help='''Return immediately if the stored
                        variable is newer than this timestamp.''',
                        type=arg_parsers.Datetime.Parse)

    parser.add_argument('--max-wait',
                        help='An optional maximum number of seconds to wait.',
                        type=arg_parsers.Duration(lower_bound='1s',
                                                  upper_bound='60s'))

    parser.add_argument('name', help='Variable name.')

  def Collection(self):
    """Returns the default collection path string.

    Returns:
      The default collection path string.
    """
    return 'runtimeconfig.variables'

  def Run(self, args):
    """Run a command that watches a variable.

    Args:
      args: argparse.Namespace, The arguments that this command was invoked
          with.

    Returns:
      The WatchVariable response.

    Raises:
      HttpException: An http error response was received while executing api
          request.
    """
    # Disable retries and configure the timeout.
    variable_client = util.VariableClient(num_retries=0, timeout=args.max_wait)
    messages = util.Messages()

    var_resource = util.ParseVariableName(args.name, args)
    project = var_resource.projectsId
    config = var_resource.configsId
    name = var_resource.Name()

    if args.newer_than:
      newer_than = times.FormatDateTime(args.newer_than)
    else:
      newer_than = None

    with progress_tracker.ProgressTracker(
        'Waiting for variable [{0}] to change'.format(name)):
      try:
        return util.FormatVariable(
            variable_client.Watch(
                messages.RuntimeconfigProjectsConfigsVariablesWatchRequest(
                    projectsId=project,
                    configsId=config,
                    variablesId=name,
                    watchVariableRequest=messages.WatchVariableRequest(
                        newerThan=newer_than,
                    )
                )
            )
        )

      except apitools_exceptions.HttpError as error:
        # For deadline exceeded or bad gateway errors,
        # we return a status code of 2.
        # In some cases, the GFE will timeout before the backend
        # responds with a 504 Gateway Timeout (DEADLINE_EXCEEDED).
        # In that scenario, GFE responds first with a 502 BAD GATEWAY error.
        if util.IsDeadlineExceededError(error) or util.IsBadGatewayError(error):
          _RaiseTimeout()
        raise

      except socket.error as error:
        if util.IsSocketTimeout(error):
          _RaiseTimeout()
        raise


def _RaiseTimeout():
  raise base_exceptions.ToolException(
      'Variable did not change prior to timeout.', exit_code=2)
