from __future__ import absolute_import
import mock
import six
import os
try:
    import unittest2 as unittest
except ImportError:
    import unittest

import koji

from koji_cli.commands import handle_image_build, _build_image_oz
from . import utils

if six.PY2:
    ConfigParser = six.moves.configparser.SafeConfigParser
else:
    ConfigParser = six.moves.configparser.ConfigParser

TASK_OPTIONS = {
    "background": None,
    "disk_size": "20",
    "distro": "Fedora-26",
    "factory_parameter": [
        (
            "factory_test_ver",
            "1.0"
        )
    ],
    "format": [
        "qcow2",
        "rhevm-ova",
        "vsphere-ova"
    ],
    "kickstart": "fedora-26-server-docker.ks",
    "ksurl": "git://git.fedorahosted.org/git/spin-kickstarts.git?fedora26#68c40eb7",
    "ksversion": "DEVEL",
    "noprogress": None,
    "optional_arches": [
        "ppc",
        "arm64"
    ],
    "ova_option": [
        "vsphere_product_version=26",
        "rhevm_description=Fedora Cloud 26",
        "vsphere_product_vendor_name=Fedora Project",
        "ovf_memory_mb=6144",
        "rhevm_default_display_type=1",
        "vsphere_product_name=Fedora Cloud 26",
        "ovf_cpu_count=4",
        "rhevm_os_descriptor=Fedora-26"
    ],
    "release": None,
    "repo": [
        "https://alt.fedoraproject.org/pub/alt/releases/26/Cloud/$arch/os/"
    ],
    "scratch": None,
    "skip_tag": None,
    "specfile": "git://git.fedorahosted.org/git/spin-kickstarts.git?spec_templates/fedora26#68c40eb7",
    "wait": None,
}

def mock_open():
    """Return the right patch decorator for open"""
    if six.PY2:
        return mock.patch('__builtin__.open')
    else:
        return mock.patch('builtins.open')


class Options(object):
    def __init__(self, init_dict):
        for k, v in init_dict.items():
            setattr(self, k, v)


class TestBuildImageOz(utils.CliTestCase):

    # Show long diffs in error output...
    maxDiff = None

    def setUp(self):
        self.task_options = Options(TASK_OPTIONS)
        self.session = mock.MagicMock()
        self.options = mock.MagicMock()
        self.options.quiet = False
        self.options.poll_interval = 100
        self.options.weburl = 'https://test.org'
        self.args = [
            'fedora-server-docker',
            '26',
            'f26-candidate',
            'https://alt.fedoraproject.org/pub/alt/releases/26/Cloud/$arch/os/',
            'x86_64',
            'ppc',
            'arm64'
        ]

        self.target_info = {
            'dest_tag_name': 'f26-candidate',
            'dest_tag': 'f26-candidate'
        }

        self.tag_info = {
            'maven_support': False,
            'locked': False,
            'name': 'f26-candidate',
            'extra': {},
            'perm': None,
            'id': 2,
            'arches': 'x86_64',
            'maven_include_all': False,
            'perm_id': None
        }

        # mocks
        self.activate_session = mock.patch('koji_cli.commands.activate_session').start()
        self.watch_tasks = mock.patch('koji_cli.commands.watch_tasks').start()
        self.unique_path = mock.patch('koji_cli.commands.unique_path').start()
        self.unique_path.return_value = '/path/to/cli-image'
        self.running_in_bg = mock.patch('koji_cli.commands._running_in_bg').start()
        self.running_in_bg.return_value = False

    def tearDown(self):
        mock.patch.stopall()

    def test_build_image_oz(self):
        task_id = 101
        self.session.getBuildTarget.return_value = self.target_info
        self.session.getTag.return_value = self.tag_info
        self.session.buildImageOz.return_value = task_id
        with mock.patch('sys.stdout', new_callable=six.StringIO) as stdout:
            _build_image_oz(
                self.options, self.task_options, self.session, self.args)
        expected = "Created task: %d" % task_id + "\n"
        expected += "Task info: %s/taskinfo?taskID=%s" % \
                    (self.options.weburl, task_id) + "\n"
        self.assert_console_message(stdout, expected)
        self.watch_tasks.assert_called_with(
            self.session, [task_id],
            quiet=self.options.quiet,
            poll_interval=self.options.poll_interval)
        self.session.buildImageOz.assert_called_once()

    def test_build_image_oz_background(self):
        task_id = 105
        self.session.getBuildTarget.return_value = self.target_info
        self.session.getTag.return_value = self.tag_info
        self.session.buildImageOz.return_value = task_id
        self.task_options.background = True
        self.running_in_bg.return_value = True
        with mock.patch('sys.stdout', new_callable=six.StringIO) as stdout:
            _build_image_oz(
                self.options, self.task_options, self.session, self.args)
        expected = "Created task: %d" % task_id + "\n"
        expected += "Task info: %s/taskinfo?taskID=%s" % \
                    (self.options.weburl, task_id) + "\n"
        self.assert_console_message(stdout, expected)
        self.watch_tasks.assert_not_called()
        self.session.buildImageOz.assert_called_once()

    def test_build_image_oz_scratch(self):
        task_id = 106
        # self.task_options.kickstart will be
        # changed in _build_image_oz()
        ksfile = self.task_options.kickstart
        self.task_options.ksurl = None
        self.task_options.scratch = True

        self.session.getBuildTarget.return_value = self.target_info
        self.session.getTag.return_value = self.tag_info
        self.session.buildImageOz.return_value = task_id

        self.task_options.background = True
        self.running_in_bg.return_value = True
        with mock.patch('sys.stdout', new_callable=six.StringIO) as stdout:
            _build_image_oz(
                self.options, self.task_options, self.session, self.args)
        expected = '' + '\n'
        expected += "Created task: %d" % task_id + "\n"
        expected += "Task info: %s/taskinfo?taskID=%s" % \
                    (self.options.weburl, task_id) + "\n"
        self.assert_console_message(stdout, expected)
        self.watch_tasks.assert_not_called()
        self.session.buildImageOz.assert_called_once()
        self.unique_path.assert_called_with('cli-image')
        self.session.uploadWrapper.assert_called_with(
            ksfile,
            '/path/to/cli-image',
            callback=None)

    def test_build_image_oz_exception(self):
        self.session.getBuildTarget.return_value = {}
        with self.assertRaises(koji.GenericError) as cm:
            _build_image_oz(
                self.options, self.task_options, self.session, self.args)
        self.assertEqual(
            str(cm.exception), 'Unknown build target: %s' % self.args[2])

        self.session.getBuildTarget.return_value = self.target_info
        self.session.getTag.return_value = {}
        with self.assertRaises(koji.GenericError) as cm:
            _build_image_oz(
                self.options, self.task_options, self.session, self.args)
        self.assertEqual(
            str(cm.exception),
            'Unknown destination tag: %s' % self.target_info['dest_tag_name'])

        self.session.getTag.return_value = self.tag_info
        with self.assertRaises(koji.GenericError) as cm:
            self.task_options.ksurl = None
            self.task_options.scratch = False
            _build_image_oz(
                self.options, self.task_options, self.session, self.args)
        self.assertEqual(
            str(cm.exception),
            'Non-scratch builds must provide ksurl')


class TestImageBuild(utils.CliTestCase):

    # Show long diffs in error output...
    maxDiff = None

    def setUp(self):
        self.options = mock.MagicMock()
        self.session = mock.MagicMock()
        self.configparser = mock.patch('six.moves.configparser.ConfigParser').start()

        self.error_format = """Usage: %s image-build [options] <name> <version> <target> <install-tree-url> <arch> [<arch> ...]
       %s image-build --config <FILE>

(Specify the --help global option for a list of other help options)

%s: error: {message}
""" % (self.progname, self.progname, self.progname)

    def tearDown(self):
        mock.patch.stopall()

    @mock.patch('koji_cli.commands._build_image_oz')
    def test_handle_image_build_with_config(self, build_image_oz_mock):
        """Test handle_image_build argument with --config cases"""

        # Case 1, config file not exist case
        with self.assertRaises(koji.ConfigurationError) as cm:
            handle_image_build(self.options,
                               self.session,
                               ['--config', '/nonexistent-file-755684354'])
        self.assertEqual(cm.exception.args[0],
                         "Config file /nonexistent-file-755684354 can't be opened.")


        # Case 2, no image-build section in config file
        expected = "single section called [%s] is required" % "image-build"

        self.configparser.return_value = ConfigParser()

        self.assert_system_exit(
            handle_image_build,
            self.options,
            self.session,
            ['--config',
             os.path.join(os.path.dirname(__file__),
                          'data/image-build-config-empty.conf')],
            stderr=self.format_error_message(expected),
            activate_session=None)

        config_file = os.path.join(os.path.dirname(__file__),
                                   'data/image-build-config.conf')
        # Case 3, normal
        handle_image_build(
            self.options,
            self.session,
            ['--config', config_file])

        args, kwargs = build_image_oz_mock.call_args
        TASK_OPTIONS['config'] = config_file
        self.assertDictEqual(TASK_OPTIONS, args[1].__dict__)

    @mock.patch('koji_cli.commands.activate_session')
    def test_handle_image_build_argument_error_without_config(
            self,
            activate_session_mock):
        """Test handle_image_build argument errors, no --config cases"""

        # Case 1, empty argument error
        expected = "At least five arguments are required: a name, " + \
                   "a version, a build target, a URL to an " + \
                   "install tree, and 1 or more architectures."

        self.assert_system_exit(
                handle_image_build,
                self.options,
                self.session,
                [],
                stderr=self.format_error_message(expected),
                activate_session=None)

        # Case 2, not kickstart options (--ksurl, kickstart)
        expected = "You must specify --kickstart"

        self.assert_system_exit(
                handle_image_build,
                self.options,
                self.session,
                ['name', 'version', 'target', 'install-tree-url', 'arch'],
                stderr=self.format_error_message(expected),
                activate_session=None)

        # Case 3, no --distro
        expected = "You must specify --distro. Examples: Fedora-16, RHEL-6.4, " + \
                   "SL-6.4 or CentOS-6.4"

        self.assert_system_exit(
                handle_image_build,
                self.options,
                self.session,
                ['name', 'version', 'target', 'install-tree-url', 'arch',
                 '--kickstart', 'kickstart.ks'],
                stderr=self.format_error_message(expected),
                activate_session=None)

        # activate_session() should not be called
        activate_session_mock.assert_not_called()

    def test_handle_image_build_help(self):
        """Test handle_image_build help message"""
        self.assert_help(
            handle_image_build,
            """Usage: %s image-build [options] <name> <version> <target> <install-tree-url> <arch> [<arch> ...]
       %s image-build --config <FILE>

(Specify the --help global option for a list of other help options)

Options:
  -h, --help            show this help message and exit
  --background          Run the image creation task at a lower priority
  --config=CONFIG       Use a configuration file to define image-build options
                        instead of command line options (they will be
                        ignored).
  --disk-size=DISK_SIZE
                        Set the disk device size in gigabytes
  --distro=DISTRO       specify the RPM based distribution the image will be
                        based on with the format RHEL-X.Y, CentOS-X.Y, SL-X.Y,
                        or Fedora-NN. The packages for the Distro you choose
                        must have been built in this system.
  --format=FORMAT       Convert results to one or more formats (vmdk, qcow,
                        qcow2, vdi, vpc, rhevm-ova, vsphere-ova, vagrant-
                        virtualbox, vagrant-libvirt, vagrant-vmware-fusion,
                        vagrant-hyperv, docker, raw-xz, liveimg-squashfs, tar-
                        gz), this option may be used multiple times. By
                        default, specifying this option will omit the raw disk
                        image (which is 10G in size) from the build results.
                        If you really want it included with converted images,
                        pass in 'raw' as an option.
  --kickstart=KICKSTART
                        Path to a local kickstart file
  --ksurl=SCMURL        The URL to the SCM containing the kickstart file
  --ksversion=VERSION   The syntax version used in the kickstart file
  --noprogress          Do not display progress of the upload
  --nowait              Don't wait on image creation
  --ova-option=OVA_OPTION
                        Override a value in the OVA description XML. Provide a
                        value in a name=value format, such as
                        'ovf_memory_mb=6144'
  --factory-parameter=FACTORY_PARAMETER
                        Pass a parameter to Image Factory. The results are
                        highly specific to the image format being created.
                        This is a two argument parameter that can be specified
                        an arbitrary number of times. For example: --factory-
                        parameter docker_cmd '[ "/bin/echo Hello World" ]'
  --release=RELEASE     Forcibly set the release field
  --repo=REPO           Specify a repo that will override the repo used to
                        install RPMs in the image. May be used multiple times.
                        The build tag repo associated with the target is the
                        default.
  --scratch             Create a scratch image
  --skip-tag            Do not attempt to tag package
  --can-fail=ARCH1,ARCH2,...
                        List of archs which are not blocking for build
                        (separated by commas.
  --specfile=URL        SCM URL to spec file fragment to use to generate
                        wrapper RPMs
  --wait                Wait on the image creation, even if running in the
                        background
""" % (self.progname, self.progname))


if __name__ == '__main__':
    unittest.main()
