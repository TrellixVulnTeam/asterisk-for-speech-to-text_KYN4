# Copyright 2015 Google Inc. All Rights Reserved.
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
"""Command for listing service account keys."""

import textwrap

from apitools.base.py import exceptions

from googlecloudsdk.api_lib.iam import utils
from googlecloudsdk.calliope import arg_parsers
from googlecloudsdk.calliope import base
from googlecloudsdk.command_lib.iam import base_classes
from googlecloudsdk.core.util import times


class List(base_classes.BaseIamCommand, base.ListCommand):
  """List the keys for a service account."""

  detailed_help = {
      'DESCRIPTION': '{description}',
      'EXAMPLES': textwrap.dedent("""\
          To list all user-managed keys created before noon on July 19th, 2015
          (to perform key rotation, for example), run:

            $ {command} --iam-account my-iam-account@somedomain.com --managed-by user --created-before 2015-07-19T12:00:00Z
          """),
  }

  @staticmethod
  def Args(parser):
    parser.add_argument('--managed-by',
                        choices=['user', 'system', 'any'],
                        default='any',
                        help='The types of keys to list.')

    parser.add_argument(
        '--created-before',
        type=arg_parsers.Datetime.Parse,
        help=('Return only keys created before the specified time. '
              'Common time formats are accepted. This is equivalent to '
              '--filter="validAfterTime<DATE_TIME".'))

    parser.add_argument('--iam-account',
                        required=True,
                        help='A textual name to display for the account.')

  def Collection(self):
    return 'iam.service_accounts.keys'

  def Run(self, args):
    try:
      result = self.iam_client.projects_serviceAccounts_keys.List(
          self.messages.IamProjectsServiceAccountsKeysListRequest(
              name=utils.EmailToAccountResourceName(args.iam_account),
              keyTypes=utils.ManagedByFromString(args.managed_by)))

      keys = result.keys
      if args.created_before:
        ts = args.created_before
        keys = [key
                for key in keys
                if times.ParseDateTime(key.validAfterTime) < ts]

      return keys
    except exceptions.HttpError as error:
      raise utils.ConvertToServiceAccountException(error, args.iam_account)
