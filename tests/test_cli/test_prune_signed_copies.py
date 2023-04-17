from __future__ import absolute_import

import koji
import mock
import os
import six
import time

from koji_cli.commands import handle_prune_signed_copies
from . import utils


class TestPruneSignedCopies(utils.CliTestCase):

    def setUp(self):
        self.maxDiff = None
        self.original_timezone = os.environ.get('TZ')
        os.environ['TZ'] = 'US/Eastern'
        time.tzset()
        self.options = mock.MagicMock()
        self.options.debug = False
        self.session = mock.MagicMock()
        self.session.getAPIVersion.return_value = koji.API_VERSION
        self.activate_session_mock = mock.patch('koji_cli.commands.activate_session').start()
        self.error_format = """Usage: %s prune-signed-copies [options]
(Specify the --help global option for a list of other help options)

%s: error: {message}
""" % (self.progname, self.progname)

    def tearDown(self):
        if self.original_timezone is None:
            del os.environ['TZ']
        else:
            os.environ['TZ'] = self.original_timezone
        time.tzset()
        mock.patch.stopall()

    def test_handle_prune_signed_copies_help(self):
        self.assert_help(
            handle_prune_signed_copies,
            """Usage: %s prune-signed-copies [options]
(Specify the --help global option for a list of other help options)

Options:
  -h, --help            show this help message and exit
  -n, --test            Test mode
  -v, --verbose         Be more verbose
  --days=DAYS           Timeout before clearing
  -p PACKAGE, --package=PACKAGE, --pkg=PACKAGE
                        Limit to a single package
  -b BUILD, --build=BUILD
                        Limit to a single build
  -i IGNORE_TAG, --ignore-tag=IGNORE_TAG
                        Ignore these tags when considering whether a build
                        is/was latest
  --ignore-tag-file=IGNORE_TAG_FILE
                        File to read tag ignore patterns from
  -r PROTECT_TAG, --protect-tag=PROTECT_TAG
                        Do not prune signed copies from matching tags
  --protect-tag-file=PROTECT_TAG_FILE
                        File to read tag protect patterns from
  --trashcan-tag=TRASHCAN_TAG
                        Specify trashcan tag
""" % self.progname)

    def test_handle_prune_signes_copies_non_exist_build(self):
        build_id = '123'
        arguments = ['--build', build_id]
        self.session.getBuild.return_value = None
        self.assert_system_exit(
            handle_prune_signed_copies,
            self.options, self.session, arguments,
            stdout='',
            stderr=self.format_error_message("No such build: %s" % build_id),
            exit_code=2,
            activate_session=None)
        self.activate_session_mock.assert_called_once_with(self.session, self.options)
        self.session.getBuild.assert_called_once_with(build_id)

    @mock.patch('time.time', return_value=1681043424)
    @mock.patch('koji.pathinfo.build', return_value='fakebuildpath')
    @mock.patch('sys.stdout', new_callable=six.StringIO)
    def test_handle_prune_signes_copies_with_package_verbose_debug(
            self, stdout, pathinfobuild, time_time):
        """Returns info about 1 build, 4 tags, 0 files, 0 bytes and ignoring trashcan tag,
        ignored tag and info about protected tag"""
        self.options.debug = True
        arguments = ['--verbose', '--package', 'package-name', '--trashcan-tag', 'test-tag1',
                     '--protect-tag', 'test-tag3', '--ignore-tag', 'test-tag2']
        self.session.getPackage.return_value = {'id': 135, 'name': 'package-name'}
        self.session.listBuilds.side_effect = [[{'build_id': 1, 'nvr': 'package-name-1.3-4',
                                                 'package_name': 'package-name'}], []]
        self.session.queryHistory.side_effect = [
            {'tag_listing': [{'tag.name': 'test-tag1'}, {'tag.name': 'test-tag2'},
                             {'tag.name': 'test-tag3'}, {'tag.name': 'test-tag4'}]},
            {'tag_listing': [{'active': True, 'build_id': 1, 'create_event': 11,
                              'create_ts': 1681191826, 'name': 'package-name', 'release': '4',
                              'revoke_event': None, 'tag_name': 'test-tag4', 'version': '1.3'},
                             {'active': True, 'build_id': 1, 'create_event': 11,
                              'create_ts': 1681191826, 'name': 'package-name', 'release': '4',
                              'revoke_event': 22, 'revoke_ts': 1681191836, 'tag_name': 'test-tag3',
                              'version': '1.3'}]}]
        rv = handle_prune_signed_copies(self.options, self.session, arguments)
        actual = stdout.getvalue()
        expected = """Cutoff date: Tue Apr  4 08:30:24 2023
Getting builds...
...got 1 builds
DEBUG: package-name-1.3-4
Tags: ['test-tag1', 'test-tag2', 'test-tag3', 'test-tag4']
Ignoring trashcan tag for build package-name-1.3-4
Ignoring tag test-tag2 for build package-name-1.3-4
Tue Apr 11 01:43:46 2023: Tagged package-name-1.3-4 with test-tag3 [still active]
Build package-name-1.3-4 had protected tag test-tag3 until Tue Apr 11 01:43:56 2023
--- Grand Totals ---
Files: 0
Bytes: 0
"""
        self.assertMultiLineEqual(actual, expected)
        self.assertNotEqual(rv, 1)
        self.activate_session_mock.assert_called_once_with(self.session, self.options)
        self.session.getBuild.assert_not_called()
        self.session.getPackage.assert_called_once_with('package-name')

    @mock.patch('time.asctime', return_value='Sat Apr  1 14:08:17 2023')
    @mock.patch('koji.pathinfo.build', return_value='fakebuildpath')
    @mock.patch('sys.stdout', new_callable=six.StringIO)
    def test_handle_prune_signes_copies_latest_tag(self, stdout, pathinfobuild, timeasctime):
        """Returns prune signed copies info with package latest tag"""
        self.options.debug = True
        arguments = ['--verbose', '--package', 'package-name']
        self.session.getPackage.return_value = {'id': 135, 'name': 'package-name'}
        self.session.listBuilds.side_effect = [
            [{'build_id': 1, 'nvr': 'package-name-1.3-4', 'package_name': 'package-name'}], []]
        self.session.queryHistory.side_effect = [
            {'tag_listing': [{'tag.name': 'test-tag1'}, {'tag.name': 'test-tag2'}]},
            {'tag_listing': [{'active': True, 'build_id': 1, 'create_event': 11,
                              'create_ts': 1681191826, 'name': 'package-name', 'release': '4',
                              'revoke_event': None, 'tag_name': 'test-tag1', 'version': '1.3'}]}]
        rv = handle_prune_signed_copies(self.options, self.session, arguments)
        actual = stdout.getvalue()
        expected = """Cutoff date: Sat Apr  1 14:08:17 2023
Getting builds...
...got 1 builds
DEBUG: package-name-1.3-4
Tags: ['test-tag1', 'test-tag2']
Sat Apr  1 14:08:17 2023: Tagged package-name-1.3-4 with test-tag1 [still active]
package-name-1.3-4 is latest in tag test-tag1
--- Grand Totals ---
Files: 0
Bytes: 0
"""
        self.assertMultiLineEqual(actual, expected)
        self.assertNotEqual(rv, 1)
        self.activate_session_mock.assert_called_once_with(self.session, self.options)
        self.session.getBuild.assert_not_called()
        self.session.getPackage.assert_called_once_with('package-name')

    @mock.patch('time.time', return_value=1681043424)
    @mock.patch('koji.pathinfo.build', return_value='fakebuildpath')
    @mock.patch('sys.stdout', new_callable=six.StringIO)
    def test_handle_prune_signes_copies_cutoff_package(self, stdout, pathinfobuild, time_time):
        """Returns prune signed copies info with cutoff package"""
        self.options.debug = True
        arguments = ['--verbose', '--package', 'package-name']
        self.session.getPackage.return_value = {'id': 135, 'name': 'package-name'}
        self.session.listBuilds.side_effect = [
            [{'build_id': 1, 'nvr': 'package-name-1.3-4', 'package_name': 'package-name'}], []]
        self.session.queryHistory.side_effect = [
            {'tag_listing': [{'tag.name': 'test-tag1'}, {'tag.name': 'test-tag2'}]},
            {'tag_listing': [{'active': True, 'build_id': 1, 'create_event': 11,
                              'create_ts': 1681191826, 'name': 'package-name', 'release': '4',
                              'revoke_event': 22, 'revoke_ts': 1681191836, 'tag_name': 'test-tag1',
                              'version': '1.3'},
                             {'active': True, 'build_id': 1, 'create_event': 33,
                              'create_ts': 1681191846, 'name': 'package-name', 'release': '4',
                              'revoke_event': 44, 'revoke_ts': 1681191856, 'tag_name': 'test-tag1',
                              'version': '1.3'}]}]
        rv = handle_prune_signed_copies(self.options, self.session, arguments)
        actual = stdout.getvalue()
        expected = """Cutoff date: Tue Apr  4 08:30:24 2023
Getting builds...
...got 1 builds
DEBUG: package-name-1.3-4
Tags: ['test-tag1', 'test-tag2']
Tue Apr 11 01:44:06 2023: Tagged package-name-1.3-4 with test-tag1 [still active]
Tue Apr 11 01:44:16 2023: Untagged package-name-1.3-4 from test-tag1
tag test-tag1: package-name-1.3-4 not latest (revoked Tue Apr 11 01:44:16 2023)
package-name-1.3-4 was latest past the cutoff
--- Grand Totals ---
Files: 0
Bytes: 0
"""
        self.assertMultiLineEqual(actual, expected)
        self.assertNotEqual(rv, 1)
        self.activate_session_mock.assert_called_once_with(self.session, self.options)
        self.session.getBuild.assert_not_called()
        self.session.getPackage.assert_called_once_with('package-name')

    def __vm(self, result):
        m = koji.VirtualCall('mcall_method', [], {})
        if isinstance(result, dict) and result.get('faultCode'):
            m._result = result
        else:
            m._result = (result,)
        return m

    @mock.patch('time.time', return_value=1682063424)
    @mock.patch('time.asctime', return_value='Sat Apr  20 14:08:17 2023')
    @mock.patch('koji.pathinfo.build', return_value='fakebuildpath')
    @mock.patch('sys.stdout', new_callable=six.StringIO)
    def test_handle_prune_signes_copies_without_signatures(
            self, stdout, pathinfobuild, timeasctime, timetime):
        """Returns prune signed copies info without signatures"""
        self.options.debug = True
        arguments = ['--verbose', '--package', 'package-name']
        list_rpms = [{'id': 123, 'name': 'test', 'version': '1.3', 'release': 1,
                      'arch': 'test-arch', 'external_repo_name': 'ext-repo',
                      'external_repo_id': 456, 'build_id': 1}]
        self.session.getPackage.return_value = {'id': 135, 'name': 'package-name'}
        self.session.listBuilds.side_effect = [
            [{'build_id': 1, 'nvr': 'package-name-1.3-4', 'package_name': 'package-name'}], []]
        self.session.queryHistory.side_effect = [
            {'tag_listing': [{'tag.name': 'test-tag1'}, {'tag.name': 'test-tag2'}]},
            {'tag_listing': [{'active': True, 'build_id': 1, 'create_event': 11,
                              'create_ts': 1681191826, 'name': 'package-name', 'release': '4',
                              'revoke_event': 22, 'revoke_ts': 1681191836, 'tag_name': 'test-tag1',
                              'version': '1.3'},
                             {'active': True, 'build_id': 1, 'create_event': 33,
                              'create_ts': 1681191846, 'name': 'package-name', 'release': '4',
                              'revoke_event': 44, 'revoke_ts': 1681191856, 'tag_name': 'test-tag1',
                              'version': '1.3'}]},
            {'tag_listing': [{'active': True, 'build_id': 1, 'create_event': 11,
                              'create_ts': 1681191826, 'name': 'package-name', 'release': '4',
                              'revoke_event': 22, 'revoke_ts': 1681191836, 'tag_name': 'test-tag2',
                              'version': '1.3'},
                             {'active': True, 'build_id': 1, 'create_event': 33,
                              'create_ts': 1681191846, 'name': 'package-name', 'release': '4',
                              'revoke_event': 44, 'revoke_ts': 1681191856, 'tag_name': 'test-tag2',
                              'version': '1.3'}]}]
        self.session.listRPMs.return_value = list_rpms
        self.session.multiCall.return_value = [[[]]]
        rv = handle_prune_signed_copies(self.options, self.session, arguments)
        actual = stdout.getvalue()
        expected = """Cutoff date: Sat Apr  20 14:08:17 2023
Getting builds...
...got 1 builds
DEBUG: package-name-1.3-4
Tags: ['test-tag1', 'test-tag2']
Sat Apr  20 14:08:17 2023: Tagged package-name-1.3-4 with test-tag1 [still active]
Sat Apr  20 14:08:17 2023: Untagged package-name-1.3-4 from test-tag1
tag test-tag1: package-name-1.3-4 not latest (revoked Sat Apr  20 14:08:17 2023)
Sat Apr  20 14:08:17 2023: Tagged package-name-1.3-4 with test-tag2 [still active]
Sat Apr  20 14:08:17 2023: Untagged package-name-1.3-4 from test-tag2
tag test-tag2: package-name-1.3-4 not latest (revoked Sat Apr  20 14:08:17 2023)
(build has no signatures)
--- Grand Totals ---
Files: 0
Bytes: 0
"""
        self.assertMultiLineEqual(actual, expected)
        self.assertNotEqual(rv, 1)
        self.activate_session_mock.assert_called_once_with(self.session, self.options)
        self.session.getBuild.assert_not_called()
        self.session.getPackage.assert_called_once_with('package-name')

    @mock.patch('stat.S_ISREG')
    @mock.patch('os.lstat')
    @mock.patch('time.time', return_value=1682063424)
    @mock.patch('time.asctime', return_value='Sat Apr  20 14:08:17 2023')
    @mock.patch('koji.pathinfo.build', return_value='fakebuildpath')
    @mock.patch('sys.stdout', new_callable=six.StringIO)
    def test_handle_prune_signes_copies_not_regular_file(
            self, stdout, pathinfobuild, timeasctime, timetime, lstat, isreg):
        """Returns prune signed copies info without regular file info"""
        self.options.debug = True
        arguments = ['--verbose', '--package', 'package-name']
        list_rpms = [{'id': 123, 'name': 'test', 'version': '1.3', 'release': 1,
                      'arch': 'test-arch', 'external_repo_name': 'ext-repo',
                      'external_repo_id': 456, 'build_id': 1}]
        self.session.getPackage.return_value = {'id': 135, 'name': 'package-name'}
        self.session.listBuilds.side_effect = [
            [{'build_id': 1, 'nvr': 'package-name-1.3-4', 'package_name': 'package-name'}], []]
        self.session.queryHistory.side_effect = [
            {'tag_listing': [{'tag.name': 'test-tag1'}, {'tag.name': 'test-tag2'}]},
            {'tag_listing': [{'active': True, 'build_id': 1, 'create_event': 11,
                              'create_ts': 1681191826, 'name': 'package-name', 'release': '4',
                              'revoke_event': 22, 'revoke_ts': 1681191836, 'tag_name': 'test-tag1',
                              'version': '1.3'},
                             {'active': True, 'build_id': 1, 'create_event': 33,
                              'create_ts': 1681191846, 'name': 'package-name', 'release': '4',
                              'revoke_event': 44, 'revoke_ts': 1681191856, 'tag_name': 'test-tag1',
                              'version': '1.3'}]},
            {'tag_listing': [{'active': True, 'build_id': 1, 'create_event': 11,
                              'create_ts': 1681191826, 'name': 'package-name', 'release': '4',
                              'revoke_event': 22, 'revoke_ts': 1681191836, 'tag_name': 'test-tag2',
                              'version': '1.3'},
                             {'active': True, 'build_id': 1, 'create_event': 33,
                              'create_ts': 1681191846, 'name': 'package-name', 'release': '4',
                              'revoke_event': 44, 'revoke_ts': 1681191856, 'tag_name': 'test-tag2',
                              'version': '1.3'}]}
        ]
        self.session.listRPMs.return_value = list_rpms
        sigRpm = [[[{'rpm_id': 123, 'sigkey': 'qwertyuiop'}]]]
        self.session.multiCall.return_value = sigRpm
        stat = mock.MagicMock()
        stat.st_mode = 'mode'
        stat.st_mtime = 1683191826
        lstat.return_value = stat
        isreg.return_value = False
        rv = handle_prune_signed_copies(self.options, self.session, arguments)
        actual = stdout.getvalue()
        expected = """Cutoff date: Sat Apr  20 14:08:17 2023
Getting builds...
...got 1 builds
DEBUG: package-name-1.3-4
Tags: ['test-tag1', 'test-tag2']
Sat Apr  20 14:08:17 2023: Tagged package-name-1.3-4 with test-tag1 [still active]
Sat Apr  20 14:08:17 2023: Untagged package-name-1.3-4 from test-tag1
tag test-tag1: package-name-1.3-4 not latest (revoked Sat Apr  20 14:08:17 2023)
Sat Apr  20 14:08:17 2023: Tagged package-name-1.3-4 with test-tag2 [still active]
Sat Apr  20 14:08:17 2023: Untagged package-name-1.3-4 from test-tag2
tag test-tag2: package-name-1.3-4 not latest (revoked Sat Apr  20 14:08:17 2023)
Skipping fakebuildpath/data/signed/qwertyuiop/test-arch/test-1.3-1.test-arch.rpm. Not a regular file
(build has no signed copies)
--- Grand Totals ---
Files: 0
Bytes: 0
"""
        self.assertMultiLineEqual(actual, expected)
        self.assertNotEqual(rv, 1)
        self.activate_session_mock.assert_called_once_with(self.session, self.options)
        self.session.getBuild.assert_not_called()
        self.session.getPackage.assert_called_once_with('package-name')

    @mock.patch('stat.S_ISREG')
    @mock.patch('os.lstat')
    @mock.patch('time.time', return_value=1682063424)
    @mock.patch('time.asctime', return_value='Sat Apr  20 14:08:17 2023')
    @mock.patch('koji.pathinfo.build', return_value='fakebuildpath')
    @mock.patch('sys.stdout', new_callable=six.StringIO)
    def test_handle_prune_signes_copies_file_newer(
            self, stdout, pathinfobuild, timeasctime, timetime, lstat, isreg):
        """Returns prune signed copies info with file newer info"""
        self.options.debug = True
        arguments = ['--verbose', '--package', 'package-name']
        list_rpms = [{'id': 123, 'name': 'test', 'version': '1.3', 'release': 1,
                      'arch': 'test-arch', 'external_repo_name': 'ext-repo',
                      'external_repo_id': 456, 'build_id': 1}]
        self.session.getPackage.return_value = {'id': 135, 'name': 'package-name'}
        self.session.listBuilds.side_effect = [
            [{'build_id': 1, 'nvr': 'package-name-1.3-4', 'package_name': 'package-name'}], []]
        self.session.queryHistory.side_effect = [
            {'tag_listing': [{'tag.name': 'test-tag1'}, {'tag.name': 'test-tag2'}]},
            {'tag_listing': [{'active': True, 'build_id': 1, 'create_event': 11,
                              'create_ts': 1681191826, 'name': 'package-name', 'release': '4',
                              'revoke_event': 22, 'revoke_ts': 1681191836, 'tag_name': 'test-tag1',
                              'version': '1.3'},
                             {'active': True, 'build_id': 1, 'create_event': 33,
                              'create_ts': 1681191846, 'name': 'package-name', 'release': '4',
                              'revoke_event': 44, 'revoke_ts': 1681191856, 'tag_name': 'test-tag1',
                              'version': '1.3'}]},
            {'tag_listing': [{'active': True, 'build_id': 1, 'create_event': 11,
                              'create_ts': 1681191826, 'name': 'package-name', 'release': '4',
                              'revoke_event': 22, 'revoke_ts': 1681191836, 'tag_name': 'test-tag2',
                              'version': '1.3'},
                             {'active': True, 'build_id': 1, 'create_event': 33,
                              'create_ts': 1681191846, 'name': 'package-name', 'release': '4',
                              'revoke_event': 44, 'revoke_ts': 1681191856, 'tag_name': 'test-tag2',
                              'version': '1.3'}]}
        ]
        self.session.listRPMs.return_value = list_rpms
        sigRpm = [[[{'rpm_id': 123, 'sigkey': 'qwertyuiop'}]]]
        self.session.multiCall.return_value = sigRpm
        stat = mock.MagicMock()
        stat.st_mode = 'mode'
        stat.st_mtime = 1683191826
        lstat.return_value = stat
        isreg.return_value = True
        rv = handle_prune_signed_copies(self.options, self.session, arguments)
        actual = stdout.getvalue()
        expected = """Cutoff date: Sat Apr  20 14:08:17 2023
Getting builds...
...got 1 builds
DEBUG: package-name-1.3-4
Tags: ['test-tag1', 'test-tag2']
Sat Apr  20 14:08:17 2023: Tagged package-name-1.3-4 with test-tag1 [still active]
Sat Apr  20 14:08:17 2023: Untagged package-name-1.3-4 from test-tag1
tag test-tag1: package-name-1.3-4 not latest (revoked Sat Apr  20 14:08:17 2023)
Sat Apr  20 14:08:17 2023: Tagged package-name-1.3-4 with test-tag2 [still active]
Sat Apr  20 14:08:17 2023: Untagged package-name-1.3-4 from test-tag2
tag test-tag2: package-name-1.3-4 not latest (revoked Sat Apr  20 14:08:17 2023)
Skipping fakebuildpath/data/signed/qwertyuiop/test-arch/test-1.3-1.test-arch.rpm. File newer than cutoff
(build has no signed copies)
--- Grand Totals ---
Files: 0
Bytes: 0
"""
        self.assertMultiLineEqual(actual, expected)
        self.assertNotEqual(rv, 1)
        self.activate_session_mock.assert_called_once_with(self.session, self.options)
        self.session.getBuild.assert_not_called()
        self.session.getPackage.assert_called_once_with('package-name')

    @mock.patch('stat.S_ISREG')
    @mock.patch('os.lstat')
    @mock.patch('time.time', return_value=1682063424)
    @mock.patch('time.asctime', return_value='Sat Apr  20 14:08:17 2023')
    @mock.patch('koji.pathinfo.build', return_value='fakebuildpath')
    @mock.patch('sys.stdout', new_callable=six.StringIO)
    def test_handle_prune_signes_copies_with_test(
            self, stdout, pathinfobuild, timeasctime, timetime, lstat, isreg):
        """Returns prune signed copies info with test option"""
        self.options.debug = True
        arguments = ['--verbose', '--package', 'package-name', '--test']
        list_rpms = [{'id': 123, 'name': 'test', 'version': '1.3', 'release': 1,
                      'arch': 'test-arch', 'external_repo_name': 'ext-repo',
                      'external_repo_id': 456, 'build_id': 1}]
        self.session.getPackage.return_value = {'id': 135, 'name': 'package-name'}
        self.session.listBuilds.side_effect = [
            [{'build_id': 1, 'nvr': 'package-name-1.3-4', 'package_name': 'package-name'}], []]
        self.session.queryHistory.side_effect = [
            {'tag_listing': [{'tag.name': 'test-tag1'}, {'tag.name': 'test-tag2'}]},
            {'tag_listing': [{'active': True, 'build_id': 1, 'create_event': 11,
                              'create_ts': 1681191826, 'name': 'package-name', 'release': '4',
                              'revoke_event': 22, 'revoke_ts': 1681191836, 'tag_name': 'test-tag1',
                              'version': '1.3'},
                             {'active': True, 'build_id': 1, 'create_event': 33,
                              'create_ts': 1681191846, 'name': 'package-name', 'release': '4',
                              'revoke_event': 44, 'revoke_ts': 1681191856, 'tag_name': 'test-tag1',
                              'version': '1.3'}]},
            {'tag_listing': [{'active': True, 'build_id': 1, 'create_event': 11,
                              'create_ts': 1681191826, 'name': 'package-name', 'release': '4',
                              'revoke_event': 22, 'revoke_ts': 1681191836, 'tag_name': 'test-tag2',
                              'version': '1.3'},
                             {'active': True, 'build_id': 1, 'create_event': 33,
                              'create_ts': 1681191846, 'name': 'package-name', 'release': '4',
                              'revoke_event': 44, 'revoke_ts': 1681191856, 'tag_name': 'test-tag2',
                              'version': '1.3'}]}
        ]
        self.session.listRPMs.return_value = list_rpms
        sigRpm = [[[{'rpm_id': 123, 'sigkey': 'qwertyuiop'}]]]
        self.session.multiCall.return_value = sigRpm
        stat = mock.MagicMock()
        stat.st_mode = 'mode'
        stat.st_mtime = 1681191826
        lstat.return_value = stat
        isreg.return_value = True
        rv = handle_prune_signed_copies(self.options, self.session, arguments)
        actual = stdout.getvalue()
        expected = """Cutoff date: Sat Apr  20 14:08:17 2023
Getting builds...
...got 1 builds
DEBUG: package-name-1.3-4
Tags: ['test-tag1', 'test-tag2']
Sat Apr  20 14:08:17 2023: Tagged package-name-1.3-4 with test-tag1 [still active]
Sat Apr  20 14:08:17 2023: Untagged package-name-1.3-4 from test-tag1
tag test-tag1: package-name-1.3-4 not latest (revoked Sat Apr  20 14:08:17 2023)
Sat Apr  20 14:08:17 2023: Tagged package-name-1.3-4 with test-tag2 [still active]
Sat Apr  20 14:08:17 2023: Untagged package-name-1.3-4 from test-tag2
tag test-tag2: package-name-1.3-4 not latest (revoked Sat Apr  20 14:08:17 2023)
Would have unlinked: fakebuildpath/data/signed/qwertyuiop/test-arch/test-1.3-1.test-arch.rpm
Would have removed dir: fakebuildpath/data/signed/qwertyuiop/test-arch
Would have removed dir: fakebuildpath/data/signed/qwertyuiop
Build: package-name-1.3-4, Removed 1 signed copies (1 bytes). Total: 1/1
--- Grand Totals ---
Files: 1
Bytes: 1
"""
        self.assertMultiLineEqual(actual, expected)
        self.assertNotEqual(rv, 1)
        self.activate_session_mock.assert_called_once_with(self.session, self.options)
        self.session.getBuild.assert_not_called()
        self.session.getPackage.assert_called_once_with('package-name')

    @mock.patch('os.unlink', return_value=None)
    @mock.patch('os.rmdir', return_value=None)
    @mock.patch('stat.S_ISREG')
    @mock.patch('os.lstat')
    @mock.patch('time.time', return_value=1682063424)
    @mock.patch('time.asctime', return_value='Sat Apr  20 14:08:17 2023')
    @mock.patch('koji.pathinfo.build', return_value='fakebuildpath')
    @mock.patch('sys.stdout', new_callable=six.StringIO)
    def test_handle_prune_signes_copies_with_verbose_removing(
            self, stdout, pathinfobuild, timeasctime, timetime, lstat, isreg, rmdir, unlink):
        """Returns prune signed copies info with verbose option and removing files/dirs"""
        self.options.debug = True
        arguments = ['--verbose', '--package', 'package-name']
        list_rpms = [{'id': 123, 'name': 'test', 'version': '1.3', 'release': 1,
                      'arch': 'test-arch', 'external_repo_name': 'ext-repo',
                      'external_repo_id': 456, 'build_id': 1}]
        self.session.getPackage.return_value = {'id': 135, 'name': 'package-name'}
        self.session.listBuilds.side_effect = [
            [{'build_id': 1, 'nvr': 'package-name-1.3-4', 'package_name': 'package-name'}], []]
        self.session.queryHistory.side_effect = [
            {'tag_listing': [{'tag.name': 'test-tag1'}, {'tag.name': 'test-tag2'}]},
            {'tag_listing': [{'active': True, 'build_id': 1, 'create_event': 11,
                              'create_ts': 1681191826, 'name': 'package-name', 'release': '4',
                              'revoke_event': 22, 'revoke_ts': 1681191836, 'tag_name': 'test-tag1',
                              'version': '1.3'},
                             {'active': True, 'build_id': 1, 'create_event': 33,
                              'create_ts': 1681191846, 'name': 'package-name', 'release': '4',
                              'revoke_event': 44, 'revoke_ts': 1681191856, 'tag_name': 'test-tag1',
                              'version': '1.3'}]},
            {'tag_listing': [{'active': True, 'build_id': 1, 'create_event': 11,
                              'create_ts': 1681191826, 'name': 'package-name', 'release': '4',
                              'revoke_event': 22, 'revoke_ts': 1681191836, 'tag_name': 'test-tag2',
                              'version': '1.3'},
                             {'active': True, 'build_id': 1, 'create_event': 33,
                              'create_ts': 1681191846, 'name': 'package-name', 'release': '4',
                              'revoke_event': 44, 'revoke_ts': 1681191856, 'tag_name': 'test-tag2',
                              'version': '1.3'}]}]
        self.session.listRPMs.return_value = list_rpms
        sigRpm = [[[{'rpm_id': 123, 'sigkey': 'qwertyuiop'}]]]
        self.session.multiCall.return_value = sigRpm
        stat = mock.MagicMock()
        stat.st_mode = 'mode'
        stat.st_mtime = 1681191826
        lstat.return_value = stat
        isreg.return_value = True
        rv = handle_prune_signed_copies(self.options, self.session, arguments)
        actual = stdout.getvalue()
        expected = """Cutoff date: Sat Apr  20 14:08:17 2023
Getting builds...
...got 1 builds
DEBUG: package-name-1.3-4
Tags: ['test-tag1', 'test-tag2']
Sat Apr  20 14:08:17 2023: Tagged package-name-1.3-4 with test-tag1 [still active]
Sat Apr  20 14:08:17 2023: Untagged package-name-1.3-4 from test-tag1
tag test-tag1: package-name-1.3-4 not latest (revoked Sat Apr  20 14:08:17 2023)
Sat Apr  20 14:08:17 2023: Tagged package-name-1.3-4 with test-tag2 [still active]
Sat Apr  20 14:08:17 2023: Untagged package-name-1.3-4 from test-tag2
tag test-tag2: package-name-1.3-4 not latest (revoked Sat Apr  20 14:08:17 2023)
Unlinking: fakebuildpath/data/signed/qwertyuiop/test-arch/test-1.3-1.test-arch.rpm
Removing dir: fakebuildpath/data/signed/qwertyuiop/test-arch
Removing dir: fakebuildpath/data/signed/qwertyuiop
Build: package-name-1.3-4, Removed 1 signed copies (1 bytes). Total: 1/1
--- Grand Totals ---
Files: 1
Bytes: 1
"""
        self.assertMultiLineEqual(actual, expected)
        self.assertNotEqual(rv, 1)
        self.activate_session_mock.assert_called_once_with(self.session, self.options)
        self.session.getBuild.assert_not_called()
        self.session.getPackage.assert_called_once_with('package-name')

    @mock.patch('stat.S_ISREG')
    @mock.patch('os.lstat')
    @mock.patch('time.time', return_value=1682063424)
    @mock.patch('time.asctime', return_value='Sat Apr  20 14:08:17 2023')
    @mock.patch('koji.pathinfo.build', return_value='fakebuildpath')
    @mock.patch('sys.stdout', new_callable=six.StringIO)
    def test_handle_prune_signes_copies_unlink_perms_error(
            self, stdout, pathinfobuild, timeasctime, timetime, lstat, isreg):
        """Returns prune signed copies info with unlink perms error"""
        self.options.debug = True
        arguments = ['--verbose', '--package', 'package-name']
        list_rpms = [{'id': 123, 'name': 'test', 'version': '1.3', 'release': 1,
                      'arch': 'test-arch', 'external_repo_name': 'ext-repo',
                      'external_repo_id': 456, 'build_id': 1}]
        self.session.getPackage.return_value = {'id': 135, 'name': 'package-name'}
        self.session.listBuilds.side_effect = [
            [{'build_id': 1, 'nvr': 'package-name-1.3-4', 'package_name': 'package-name'}], []]
        self.session.queryHistory.side_effect = [
            {'tag_listing': [{'tag.name': 'test-tag1'}, {'tag.name': 'test-tag2'}]},
            {'tag_listing': [{'active': True, 'build_id': 1, 'create_event': 11,
                              'create_ts': 1681191826, 'name': 'package-name', 'release': '4',
                              'revoke_event': 22, 'revoke_ts': 1681191836, 'tag_name': 'test-tag1',
                              'version': '1.3'},
                             {'active': True, 'build_id': 1, 'create_event': 33,
                              'create_ts': 1681191846, 'name': 'package-name', 'release': '4',
                              'revoke_event': 44, 'revoke_ts': 1681191856, 'tag_name': 'test-tag1',
                              'version': '1.3'}]},
            {'tag_listing': [{'active': True, 'build_id': 1, 'create_event': 11,
                              'create_ts': 1681191826, 'name': 'package-name', 'release': '4',
                              'revoke_event': 22, 'revoke_ts': 1681191836, 'tag_name': 'test-tag2',
                              'version': '1.3'},
                             {'active': True, 'build_id': 1, 'create_event': 33,
                              'create_ts': 1681191846, 'name': 'package-name', 'release': '4',
                              'revoke_event': 44, 'revoke_ts': 1681191856, 'tag_name': 'test-tag2',
                              'version': '1.3'}]}
        ]
        self.session.listRPMs.return_value = list_rpms
        sigRpm = [[[{'rpm_id': 123, 'sigkey': 'qwertyuiop'}]]]
        self.session.multiCall.return_value = sigRpm
        stat = mock.MagicMock()
        stat.st_mode = 'mode'
        stat.st_mtime = 1681191826
        lstat.return_value = stat
        isreg.return_value = True
        rv = handle_prune_signed_copies(self.options, self.session, arguments)
        actual = stdout.getvalue()
        expected = """Cutoff date: Sat Apr  20 14:08:17 2023
Getting builds...
...got 1 builds
DEBUG: package-name-1.3-4
Tags: ['test-tag1', 'test-tag2']
Sat Apr  20 14:08:17 2023: Tagged package-name-1.3-4 with test-tag1 [still active]
Sat Apr  20 14:08:17 2023: Untagged package-name-1.3-4 from test-tag1
tag test-tag1: package-name-1.3-4 not latest (revoked Sat Apr  20 14:08:17 2023)
Sat Apr  20 14:08:17 2023: Tagged package-name-1.3-4 with test-tag2 [still active]
Sat Apr  20 14:08:17 2023: Untagged package-name-1.3-4 from test-tag2
tag test-tag2: package-name-1.3-4 not latest (revoked Sat Apr  20 14:08:17 2023)
Unlinking: fakebuildpath/data/signed/qwertyuiop/test-arch/test-1.3-1.test-arch.rpm
Error removing fakebuildpath/data/signed/qwertyuiop/test-arch/test-1.3-1.test-arch.rpm: [Errno 2] No such file or directory: 'fakebuildpath/data/signed/qwertyuiop/test-arch/test-1.3-1.test-arch.rpm'
This script needs write access to /mnt/koji
(build has no signed copies)
--- Grand Totals ---
Files: 0
Bytes: 0
"""
        self.assertMultiLineEqual(actual, expected)
        self.assertNotEqual(rv, 1)
        self.activate_session_mock.assert_called_once_with(self.session, self.options)
        self.session.getBuild.assert_not_called()
        self.session.getPackage.assert_called_once_with('package-name')

    @mock.patch('os.unlink', return_value=None)
    @mock.patch('stat.S_ISREG')
    @mock.patch('os.lstat')
    @mock.patch('time.time', return_value=1682063424)
    @mock.patch('time.asctime', return_value='Sat Apr  20 14:08:17 2023')
    @mock.patch('koji.pathinfo.build', return_value='fakebuildpath')
    @mock.patch('sys.stdout', new_callable=six.StringIO)
    def test_handle_prune_signes_copies_error_removing(
            self, stdout, pathinfobuild, timeasctime, timetime, lstat, isreg, unlink):
        """Returns prune signed copies info with removing error"""
        self.options.debug = True
        arguments = ['--verbose', '--package', 'package-name']
        list_rpms = [{'id': 123, 'name': 'test', 'version': '1.3', 'release': 1,
                      'arch': 'test-arch', 'external_repo_name': 'ext-repo',
                      'external_repo_id': 456, 'build_id': 1}]
        self.session.getPackage.return_value = {'id': 135, 'name': 'package-name'}
        self.session.listBuilds.side_effect = [
            [{'build_id': 1, 'nvr': 'package-name-1.3-4', 'package_name': 'package-name'}], []]
        self.session.queryHistory.side_effect = [
            {'tag_listing': [{'tag.name': 'test-tag1'}, {'tag.name': 'test-tag2'}]},
            {'tag_listing': [{'active': True, 'build_id': 1, 'create_event': 11,
                              'create_ts': 1681191826, 'name': 'package-name', 'release': '4',
                              'revoke_event': 22, 'revoke_ts': 1681191836, 'tag_name': 'test-tag1',
                              'version': '1.3'},
                             {'active': True, 'build_id': 1, 'create_event': 33,
                              'create_ts': 1681191846, 'name': 'package-name', 'release': '4',
                              'revoke_event': 44, 'revoke_ts': 1681191856, 'tag_name': 'test-tag1',
                              'version': '1.3'}]},
            {'tag_listing': [{'active': True, 'build_id': 1, 'create_event': 11,
                              'create_ts': 1681191826, 'name': 'package-name', 'release': '4',
                              'revoke_event': 22, 'revoke_ts': 1681191836, 'tag_name': 'test-tag2',
                              'version': '1.3'},
                             {'active': True, 'build_id': 1, 'create_event': 33,
                              'create_ts': 1681191846, 'name': 'package-name', 'release': '4',
                              'revoke_event': 44, 'revoke_ts': 1681191856, 'tag_name': 'test-tag2',
                              'version': '1.3'}]}
        ]
        self.session.listRPMs.return_value = list_rpms
        sigRpm = [[[{'rpm_id': 123, 'sigkey': 'qwertyuiop'}]]]
        self.session.multiCall.return_value = sigRpm
        stat = mock.MagicMock()
        stat.st_mode = 'mode'
        stat.st_mtime = 1681191826
        lstat.return_value = stat
        isreg.return_value = True
        rv = handle_prune_signed_copies(self.options, self.session, arguments)
        actual = stdout.getvalue()
        expected = """Cutoff date: Sat Apr  20 14:08:17 2023
Getting builds...
...got 1 builds
DEBUG: package-name-1.3-4
Tags: ['test-tag1', 'test-tag2']
Sat Apr  20 14:08:17 2023: Tagged package-name-1.3-4 with test-tag1 [still active]
Sat Apr  20 14:08:17 2023: Untagged package-name-1.3-4 from test-tag1
tag test-tag1: package-name-1.3-4 not latest (revoked Sat Apr  20 14:08:17 2023)
Sat Apr  20 14:08:17 2023: Tagged package-name-1.3-4 with test-tag2 [still active]
Sat Apr  20 14:08:17 2023: Untagged package-name-1.3-4 from test-tag2
tag test-tag2: package-name-1.3-4 not latest (revoked Sat Apr  20 14:08:17 2023)
Unlinking: fakebuildpath/data/signed/qwertyuiop/test-arch/test-1.3-1.test-arch.rpm
Removing dir: fakebuildpath/data/signed/qwertyuiop/test-arch
Error removing fakebuildpath/data/signed/qwertyuiop/test-arch/test-1.3-1.test-arch.rpm: [Errno 2] No such file or directory: 'fakebuildpath/data/signed/qwertyuiop/test-arch'
Removing dir: fakebuildpath/data/signed/qwertyuiop
Error removing fakebuildpath/data/signed/qwertyuiop/test-arch/test-1.3-1.test-arch.rpm: [Errno 2] No such file or directory: 'fakebuildpath/data/signed/qwertyuiop'
Build: package-name-1.3-4, Removed 1 signed copies (1 bytes). Total: 1/1
--- Grand Totals ---
Files: 1
Bytes: 1
"""
        self.assertMultiLineEqual(actual, expected)
        self.assertNotEqual(rv, 1)
        self.activate_session_mock.assert_called_once_with(self.session, self.options)
        self.session.getBuild.assert_not_called()
        self.session.getPackage.assert_called_once_with('package-name')

    @mock.patch('time.asctime', return_value='Sat Apr  1 14:08:17 2023')
    @mock.patch('koji.pathinfo.build', return_value='fakebuildpath')
    @mock.patch('sys.stdout', new_callable=six.StringIO)
    def test_handle_prune_signes_copies_not_create_event(self, stdout, pathinfobuild, timeasctime):
        self.options.debug = True
        arguments = ['--verbose', '--package', 'package-name']
        self.session.getPackage.return_value = {'id': 135, 'name': 'package-name'}
        self.session.listBuilds.side_effect = [
            [{'build_id': 1, 'nvr': 'package-name-1.3.4', 'package_name': 'package-name'}], []]
        self.session.queryHistory.side_effect = [
            {'tag_listing': [{'tag.name': 'test-tag1'}, {'tag.name': 'test-tag2'}]},
            {'tag_listing': [{'active': True, 'build_id': 1, 'create_event': None,
                              'create_ts': None, 'name': 'package-name', 'release': '4',
                              'revoke_event': None, 'revoke_ts': None, 'tag_name': 'test-tag1',
                              'version': '3'}]}]

        with self.assertRaises(koji.GenericError) as ex:
            handle_prune_signed_copies(self.options, self.session, arguments)
        self.assertEqual(str(ex.exception),
                         "No creation event found for package-name-1.3.4 in test-tag1")
        self.activate_session_mock.assert_called_once_with(self.session, self.options)
        self.session.getBuild.assert_not_called()
        self.session.getPackage.assert_called_once_with('package-name')

    def test_handle_prune_signes_copies_without_pkg_tag_history(self):
        self.options.debug = True
        arguments = ['--verbose', '--package', 'package-name']
        self.session.getPackage.return_value = {'id': 135, 'name': 'package-name'}
        self.session.listBuilds.side_effect = [
            [{'build_id': 1, 'nvr': 'package-name-1.3.4', 'package_name': 'package-name'}], []]
        self.session.queryHistory.side_effect = [
            {'tag_listing': [{'tag.name': 'test-tag1'}, {'tag.name': 'test-tag2'}]},
            {'tag_listing': []}]

        with self.assertRaises(koji.GenericError) as ex:
            handle_prune_signed_copies(self.options, self.session, arguments)
        self.assertEqual(str(ex.exception), "No history found for package-name-1.3.4 in test-tag1")
        self.activate_session_mock.assert_called_once_with(self.session, self.options)
        self.session.getBuild.assert_not_called()
        self.session.getPackage.assert_called_once_with('package-name')
