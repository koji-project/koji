from __future__ import absolute_import
import mock
import six

try:
    import unittest2 as unittest
except ImportError:
    import unittest

import koji
from koji_cli.commands import handle_spin_livecd, handle_spin_livemedia, handle_spin_appliance, _build_image
from . import utils


LIVECD_OPTIONS = {
    "background": True,
    "scratch": None,
    "wait": None,
    "noprogress": None,
    "skip_tag": False,
    "ksurl": None,
    "ksversion": None,
    "repo": None,
    "release": None,
    "volid": None,
    "specfile": None,
}

LIVEMEDIA_OPTIONS = {
    "background": True,
    "scratch": None,
    "wait": None,
    "noprogress": None,
    "skip_tag": False,
    "ksurl": None,
    "ksversion": None,
    "repo": None,
    "release": None,
    "specfile": None,
    "install_tree_url": None,
    "lorax_dir": None,
    "lorax_url": None,
    "optional_arches": None,
    "volid": None,
}

APPLIANCE_OPTIONS = {
    "background": True,
    "scratch": None,
    "wait": None,
    "noprogress": None,
    "skip_tag": False,
    "ksurl": None,
    "ksversion": None,
    "repo": None,
    "release": None,
    "specfile": None,
    "format": 'raw',
    "vcpu": None,
    "vmem": None,
}


class Options(object):
    def __init__(self, init_dict):
        for k, v in init_dict.items():
            setattr(self, k, v)


class TestBuildImage(utils.CliTestCase):

    # Show long diffs in error output...
    maxDiff = None

    def setUp(self):
        self.task_id = 1001
        self.weburl = 'https://web.url'
        self.options = mock.MagicMock()
        self.options.quiet = False
        self.options.weburl = self.weburl
        self.options.poll_interval = 10
        self.session = mock.MagicMock()
        self.arguments = ['test-image', '1', 'target', 'x86_64', 'image.ks']
        self.activate_session = mock.patch('koji_cli.commands.activate_session').start()
        self.unique_path = mock.patch('koji_cli.commands.unique_path').start()
        self.running_in_bg = mock.patch('koji_cli.commands._running_in_bg').start()
        self.watch_tasks = mock.patch('koji_cli.commands.watch_tasks').start()

        self.build_target = {
            'id': 1,
            'name': 'target',
            'dest_tag': 1,
            'build_tag': 2,
            'build_tag_name': 'target-build',
            'dest_tag_name': 'target'
        }

        self.dest_tag = {'id': 1, 'name': 'dest-tag', 'arch': 'x86_64'}

        self.session.getBuildTarget.return_value = self.build_target
        self.session.getTag.return_value = self.dest_tag
        self.session.buildImage.return_value = self.task_id
        self.unique_path.return_value = '/path/to/cli-image-indirection'
        self.running_in_bg.return_value = False
        self.watch_tasks.return_value = True

    def tearDown(self):
        mock.patch.stopall()

    def test_build_image_livecd(self):
        """Test _build_image function build livecd"""

        self.task_opts = Options(LIVECD_OPTIONS)
        self.task_opts.ksurl = 'http://somewhere.org'

        expected = "Created task: %d" % self.task_id + "\n"
        expected += "Task info: %s/taskinfo?taskID=%s" % (self.weburl, self.task_id) + "\n"

        args = [self.options, self.task_opts, self.session,
                self.arguments, 'livecd']
        with mock.patch('sys.stdout', new_callable=six.StringIO) as stdout:
            _build_image(*args)
        self.assert_console_message(stdout, expected)
        self.session.buildImage.assert_called_once()
        self.watch_tasks.assert_called_once()

    def test_build_image_appliance(self):
        """Test _build_image function build appliance"""

        self.task_opts = Options(APPLIANCE_OPTIONS)
        self.task_opts.ksurl = 'http://somewhere.org'

        expected = "Created task: %d" % self.task_id + "\n"
        expected += "Task info: %s/taskinfo?taskID=%s" % (self.weburl, self.task_id) + "\n"

        args = [self.options, self.task_opts, self.session,
                self.arguments, 'appliance']
        with mock.patch('sys.stdout', new_callable=six.StringIO) as stdout:
            _build_image(*args)
        self.assert_console_message(stdout, expected)
        self.session.buildImage.assert_called_once()
        self.watch_tasks.assert_called_once()

    def test_build_image_livemedia(self):
        """Test _build_image function build livemedia"""

        self.task_opts = Options(LIVEMEDIA_OPTIONS)
        self.task_opts.ksurl = 'http://somewhere.org'
        self.task_opts.wait = False

        expected = "Created task: %d" % self.task_id + "\n"
        expected += "Task info: %s/taskinfo?taskID=%s" % (self.weburl, self.task_id) + "\n"

        args = [self.options, self.task_opts, self.session,
                self.arguments, 'livemedia']
        with mock.patch('sys.stdout', new_callable=six.StringIO) as stdout:
            _build_image(*args)
        self.assert_console_message(stdout, expected)
        self.session.buildImage.assert_called_once()
        self.watch_tasks.assert_not_called()

    def test_build_image_livemedia_without_ksurl(self):
        """Test _build_image function build livemedia without ksurl"""

        self.task_opts = Options(LIVEMEDIA_OPTIONS)
        self.task_opts.optional_arches = 'ppc, arm64'

        expected = "\n"
        expected += "Created task: %d" % self.task_id + "\n"
        expected += "Task info: %s/taskinfo?taskID=%s" % (self.weburl, self.task_id) + "\n"

        # set return value for check
        self.watch_tasks.return_value = self.task_id

        args = [self.options, self.task_opts, self.session,
                self.arguments, 'livemedia']
        with mock.patch('sys.stdout', new_callable=six.StringIO) as stdout:
            self.assertEqual(self.task_id, _build_image(*args))
        args, kwargs = self.session.buildImage.call_args
        self.assert_console_message(stdout, expected)
        self.session.buildImage.assert_called_once()
        self.watch_tasks.assert_called_once()
        opts = kwargs['opts']
        self.assertIn('optional_arches', opts)
        self.assertEqual(
            self.task_opts.optional_arches.split(','), opts['optional_arches'])

    def test_build_image_livemedia_no_progress(self):
        """Test _build_image function build livemedia with noprogress option"""
        self.task_opts = Options(LIVEMEDIA_OPTIONS)
        self.task_opts.noprogress = True
        self.task_opts.wait = False

        expected = "\n"
        expected += "Created task: %d" % self.task_id + "\n"
        expected += "Task info: %s/taskinfo?taskID=%s" % (self.weburl, self.task_id) + "\n"

        args = [self.options, self.task_opts, self.session,
                self.arguments, 'livemedia']
        with mock.patch('sys.stdout', new_callable=six.StringIO) as stdout:
            self.assertEqual(None, _build_image(*args))
        args, kwargs = self.session.buildImage.call_args
        self.assert_console_message(stdout, expected)
        self.session.buildImage.assert_called_once()
        self.session.logout.assert_not_called()
        self.watch_tasks.assert_not_called()

    def test_build_image_expections(self):
        """Test _build_image all exceptions"""

        self.task_opts = Options(LIVEMEDIA_OPTIONS)

        # Case 1. sanity check for image type
        img_type = 'unknown_type'
        expected = 'Unrecognized image type: %s' % img_type
        args = [self.options, self.task_opts, self.session,
                self.arguments, img_type]
        with self.assertRaises(koji.GenericError) as cm:
            _build_image(*args)
        self.assertEqual(str(cm.exception), expected)
        self.activate_session.assert_not_called()

        img_type = 'livemedia'

        # Case 2. target not found error
        self.activate_session.reset_mock()
        self.session.getBuildTarget.return_value = {}
        expected = "Unknown build target: %s" % self.arguments[2]
        args[-1] = img_type
        with self.assertRaises(koji.GenericError) as cm:
            _build_image(*args)
        self.assertEqual(str(cm.exception), expected)
        self.activate_session.assert_called_with(self.session, self.options)

        # Case 3. tag not found error
        self.activate_session.reset_mock()
        self.session.getBuildTarget.return_value = self.build_target
        self.session.getTag.return_value = {}
        expected = "Unknown destination tag: %s" % self.build_target['dest_tag_name']
        args[-1] = img_type
        with self.assertRaises(koji.GenericError) as cm:
            _build_image(*args)
        self.assertEqual(str(cm.exception), expected)
        self.activate_session.assert_called_with(self.session, self.options)


class TestSpinAppliance(utils.CliTestCase):

    # Show long diffs in error output...
    maxDiff = None

    def setUp(self):
        self.options = mock.MagicMock()
        self.session = mock.MagicMock()

        self.error_format = """Usage: %s spin-appliance [options] <name> <version> <target> <arch> <kickstart-file>
(Specify the --help global option for a list of other help options)

%s: error: {message}
""" % (self.progname, self.progname)

    @mock.patch('koji_cli.commands._build_image')
    def test_handle_spin_appliance(self, build_image_mock):
        """Test handle_spin_appliance function"""
        args = ['name', 'version', 'target', 'arch', 'file.ks']
        with mock.patch('sys.stdout', new_callable=six.StringIO) as stdout:
            handle_spin_appliance(self.options, self.session, args)
        args, kwargs = build_image_mock.call_args
        empty_opts = dict((k, None) for k in APPLIANCE_OPTIONS)
        empty_opts['format'] = 'raw'
        self.assertDictEqual(empty_opts, args[1].__dict__)
        self.assertEqual(args[-1], 'appliance')

        # spin-appliance will be replaced by image-build, make sure notice message
        # has been shown
        self.assert_console_message(
            stdout, 'spin-appliance is deprecated and will be replaced with image-build\n')

    @mock.patch('koji_cli.commands._build_image')
    def test_handle_spin_appliance_argument_error(self, build_image_mock):
        """Test handle_spin_appliance function argument error"""
        # takes excatly 5 arguments
        expected = self.format_error_message(
            "Five arguments are required: a name, a version, " +
            "an architecture, a build target, and a relative path" +
            " to a kickstart file.")
        for args in [[], ['arg1', 'arg2', 'arg3', 'arg4'],
                     ['arg1', 'arg2', 'arg3', 'arg4', 'arg5', 'arg6']]:
            self.assert_system_exit(
                handle_spin_appliance,
                self.options,
                self.session,
                args,
                stderr=expected,
                activate_session=None)
        build_image_mock.assert_not_called()

    def test_handle_spin_appliance_help(self):
        """Test handle_spin_appliance help message"""
        self.assert_help(
            handle_spin_appliance,
            """Usage: %s spin-appliance [options] <name> <version> <target> <arch> <kickstart-file>
(Specify the --help global option for a list of other help options)

Options:
  -h, --help            show this help message and exit
  --wait                Wait on the appliance creation, even if running in the
                        background
  --nowait              Don't wait on appliance creation
  --noprogress          Do not display progress of the upload
  --background          Run the appliance creation task at a lower priority
  --ksurl=SCMURL        The URL to the SCM containing the kickstart file
  --ksversion=VERSION   The syntax version used in the kickstart file
  --scratch             Create a scratch appliance
  --repo=REPO           Specify a repo that will override the repo used to
                        install RPMs in the appliance. May be used multiple
                        times. The build tag repo associated with the target
                        is the default.
  --release=RELEASE     Forcibly set the release field
  --specfile=URL        SCM URL to spec file fragment to use to generate
                        wrapper RPMs
  --skip-tag            Do not attempt to tag package
  --vmem=VMEM           Set the amount of virtual memory in the appliance in
                        MB, default is 512
  --vcpu=VCPU           Set the number of virtual cpus in the appliance,
                        default is 1
  --format=DISK_FORMAT  Disk format, default is raw. Other options are qcow,
                        qcow2, and vmx.
""" % (self.progname))


class TestSpinLiveMedia(utils.CliTestCase):

    # Show long diffs in error output...
    maxDiff = None

    def setUp(self):
        self.options = mock.MagicMock()
        self.session = mock.MagicMock()

        self.error_format = """Usage: %s spin-livemedia [options] <name> <version> <target> <arch> <kickstart-file>
(Specify the --help global option for a list of other help options)

%s: error: {message}
""" % (self.progname, self.progname)

    @mock.patch('koji_cli.commands._build_image')
    def test_handle_spin_livemedia(self, build_image_mock):
        """Test handle_spin_livemedia function"""
        args = ['name', 'version', 'target', 'arch', 'file.ks']
        with mock.patch('sys.stdout', new_callable=six.StringIO):
            handle_spin_livemedia(self.options, self.session, args)
        args, kwargs = build_image_mock.call_args
        empty_opts = dict((k, None) for k in LIVEMEDIA_OPTIONS)
        empty_opts['optional_arches'] = ''
        self.assertDictEqual(empty_opts, args[1].__dict__)
        self.assertEqual(args[-1], 'livemedia')

    @mock.patch('koji_cli.commands._build_image')
    def test_handle_spin_livemedia_argument_error(self, build_image_mock):
        """Test handle_spin_livemedia function argument error"""
        # takes excatly 5 arguments
        expected = self.format_error_message(
            "Five arguments are required: a name, a version, a" +
            " build target, an architecture, and a relative path to" +
            " a kickstart file.")
        for args in [[], ['arg1', 'arg2', 'arg3', 'arg4'],
                     ['arg1', 'arg2', 'arg3', 'arg4', 'arg5', 'arg6']]:
            self.assert_system_exit(
                handle_spin_livemedia,
                self.options,
                self.session,
                args,
                stderr=expected,
                activate_session=None)
        build_image_mock.assert_not_called()

        # --lorax_url require --lorax_url option
        args = ['name', 'version', 'target', 'arch', 'file.ks',
                '--lorax_url', 'https://somewhere.org']
        expected = self.format_error_message(
            'The "--lorax_url" option requires that "--lorax_dir" also be used.')
        self.assert_system_exit(
            handle_spin_livemedia,
            self.options,
            self.session,
            args,
            stderr=expected,
            activate_session=None)
        build_image_mock.assert_not_called()

    def test_handle_spin_livemedia_help(self):
        """Test handle_spin_livemedia help message"""
        self.assert_help(
            handle_spin_livemedia,
            """Usage: %s spin-livemedia [options] <name> <version> <target> <arch> <kickstart-file>
(Specify the --help global option for a list of other help options)

Options:
  -h, --help            show this help message and exit
  --wait                Wait on the livemedia creation, even if running in the
                        background
  --nowait              Don't wait on livemedia creation
  --noprogress          Do not display progress of the upload
  --background          Run the livemedia creation task at a lower priority
  --ksurl=SCMURL        The URL to the SCM containing the kickstart file
  --install-tree-url=URL
                        Provide the URL for the install tree
  --ksversion=VERSION   The syntax version used in the kickstart file
  --scratch             Create a scratch LiveMedia image
  --repo=REPO           Specify a repo that will override the repo used to
                        install RPMs in the LiveMedia. May be used multiple
                        times. The build tag repo associated with the target
                        is the default.
  --release=RELEASE     Forcibly set the release field
  --volid=VOLID         Set the volume id
  --specfile=URL        SCM URL to spec file fragment to use to generate
                        wrapper RPMs
  --skip-tag            Do not attempt to tag package
  --can-fail=ARCH1,ARCH2,...
                        List of archs which are not blocking for build
                        (separated by commas.
  --lorax_dir=DIR       The relative path to the lorax templates directory
                        within the checkout of "lorax_url".
  --lorax_url=URL       The URL to the SCM containing any custom lorax
                        templates that are to be used to override the default
                        templates.
""" % (self.progname))


class TestSpinLiveCD(utils.CliTestCase):

    # Show long diffs in error output...
    maxDiff = None

    def setUp(self):
        self.options = mock.MagicMock()
        self.session = mock.MagicMock()

        self.error_format = """Usage: %s spin-livecd [options] <name> <version> <target> <arch> <kickstart-file>
(Specify the --help global option for a list of other help options)

%s: error: {message}
""" % (self.progname, self.progname)

    @mock.patch('koji_cli.commands._build_image')
    def test_handle_spin_livecd(self, build_image_mock):
        """Test handle_spin_livecd function"""
        args = ['name', 'version', 'target', 'arch', 'file.ks']
        with mock.patch('sys.stdout', new_callable=six.StringIO) as stdout:
            handle_spin_livecd(self.options, self.session, args)
        args, kwargs = build_image_mock.call_args
        empty_opts = dict((k, None) for k in LIVECD_OPTIONS)
        self.assertDictEqual(empty_opts, args[1].__dict__)
        self.assertEqual(args[-1], 'livecd')

        # spin-livecd will be replaced by spin-livemedia, make sure notice message
        # has been shown
        self.assert_console_message(
            stdout, 'spin-livecd is deprecated and will be replaced with spin-livemedia\n')

    @mock.patch('koji_cli.commands._build_image')
    def test_handle_spin_livecd_argument_error(self, build_image_mock):
        """Test handle_spin_livecd function argument error"""
        # takes excatly 5 arguments
        expected = self.format_error_message(
            "Five arguments are required: a name, a version, " +
            "an architecture, a build target, and a relative path to " +
            "a kickstart file.")
        for args in [[], ['arg1', 'arg2', 'arg3', 'arg4'],
                     ['arg1', 'arg2', 'arg3', 'arg4', 'arg5', 'arg6']]:
            self.assert_system_exit(
                handle_spin_livecd,
                self.options,
                self.session,
                args,
                stderr=expected,
                activate_session=None)
        build_image_mock.assert_not_called()

    def test_handle_spin_livecd_help(self):
        """Test handle_spin_livecd help message"""
        self.assert_help(
            handle_spin_livecd,
            """Usage: %s spin-livecd [options] <name> <version> <target> <arch> <kickstart-file>
(Specify the --help global option for a list of other help options)

Options:
  -h, --help           show this help message and exit
  --wait               Wait on the livecd creation, even if running in the
                       background
  --nowait             Don't wait on livecd creation
  --noprogress         Do not display progress of the upload
  --background         Run the livecd creation task at a lower priority
  --ksurl=SCMURL       The URL to the SCM containing the kickstart file
  --ksversion=VERSION  The syntax version used in the kickstart file
  --scratch            Create a scratch LiveCD image
  --repo=REPO          Specify a repo that will override the repo used to
                       install RPMs in the LiveCD. May be used multiple times.
                       The build tag repo associated with the target is the
                       default.
  --release=RELEASE    Forcibly set the release field
  --volid=VOLID        Set the volume id
  --specfile=URL       SCM URL to spec file fragment to use to generate
                       wrapper RPMs
  --skip-tag           Do not attempt to tag package
""" % (self.progname))


if __name__ == '__main__':
    unittest.main()
