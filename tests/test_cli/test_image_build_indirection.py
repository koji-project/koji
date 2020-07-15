from __future__ import absolute_import
import mock
import six
try:
    import unittest2 as unittest
except ImportError:
    import unittest

import koji

from koji_cli.commands import handle_image_build_indirection, _build_image_indirection
from . import utils


TASK_OPTIONS = {
    "background": True,
    "config": "build-image-config.conf",
    "name": "image",
    "version": "26",
    "release": "1",
    "arch": "x86_64 i386",
    "target": "target",
    "base_image_task": 2,
    "base_image_build": None,
    "utility_image_task": 4,
    "utility_image_build": None,
    "indirection_template": "template",
    "indirection_template_url": "git://git.github.org/git/",
    "results_loc": "results",
    "scratch": None,
    "wait": False,
    "noprogress": None,
    "skip_tag": False,
}


class Options(object):
    def __init__(self, init_dict):
        for k, v in init_dict.items():
            setattr(self, k, v)


class TestBuildImageIndirection(utils.CliTestCase):

    # Show long diffs in error output...
    maxDiff = None

    def setUp(self):
        self.task_id = 1001
        self.weburl = 'https://web.url'
        self.options = mock.MagicMock()
        self.options.quiet = False
        self.options.weburl = self.weburl
        self.session = mock.MagicMock()
        self.activate_session = mock.patch('koji_cli.commands.activate_session').start()
        self.unique_path = mock.patch('koji_cli.commands.unique_path').start()

        self.task_opts = Options(TASK_OPTIONS)

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
        self.session.buildImageIndirection.return_value = self.task_id
        self.unique_path.return_value = '/path/to/cli-image-indirection'

    def tearDown(self):
        mock.patch.stopall()

    def test_build_image_indirection(self):
        """Test _build_image_indirection function"""
        expected = "Created task: %d" % self.task_id + "\n"
        expected += "Task info: %s/taskinfo?taskID=%s" % (self.weburl, self.task_id) + "\n"

        with mock.patch('sys.stdout', new_callable=six.StringIO) as stdout:
            _build_image_indirection(
                self.options, self.task_opts, self.session, [])
        self.assert_console_message(stdout, expected)

    def test_build_image_indirection_with_scratch(self):
        """Test _build_image_indirection function with scratch option"""
        expected = "\n"
        expected += "Created task: %d" % self.task_id + "\n"
        expected += "Task info: %s/taskinfo?taskID=%s" % (self.weburl, self.task_id) + "\n"

        self.task_opts.indirection_template_url = None
        self.task_opts.scratch = True
        with mock.patch('sys.stdout', new_callable=six.StringIO) as stdout:
            _build_image_indirection(
                self.options, self.task_opts, self.session, [])
        self.assert_console_message(stdout, expected)

    def test_build_image_indirection_with_noprogress(self):
        """Test _build_image_indirection function with noprogress option"""
        expected = "\n"
        expected += "Created task: %d" % self.task_id + "\n"
        expected += "Task info: %s/taskinfo?taskID=%s" % (self.weburl, self.task_id) + "\n"

        self.task_opts.indirection_template_url = None
        self.task_opts.scratch = True
        self.task_opts.noprogress = True
        with mock.patch('sys.stdout', new_callable=six.StringIO) as stdout:
            _build_image_indirection(
                self.options, self.task_opts, self.session, [])
        self.assert_console_message(stdout, expected)
        args, kwargs = self.session.uploadWrapper.call_args
        self.assertEqual(kwargs['callback'], None)

    def test_build_image_indirection_expections(self):
        """Test _build_image_indirection all exceptions"""

        # Case 1. sanity check for utility image options
        self.task_opts.utility_image_task = None
        self.task_opts.utility_image_build = None
        expected = "You must specify either a utility-image task or build ID/NVR"
        with self.assertRaises(koji.GenericError) as cm:
            _build_image_indirection(
                self.options, self.task_opts, self.session, [])
        self.assertEqual(str(cm.exception), expected)
        self.activate_session.assert_not_called()

        # Case 2. sanity check for base image options
        self.task_opts.utility_image_build = 'image-utils-26.1'
        self.task_opts.base_image_task = None
        self.task_opts.base_image_build = None
        expected = "You must specify either a base-image task or build ID/NVR"
        with self.assertRaises(koji.GenericError) as cm:
            _build_image_indirection(
                self.options, self.task_opts, self.session, [])
        self.assertEqual(str(cm.exception), expected)
        self.activate_session.assert_not_called()

        self.task_opts.base_image_build = 'image-base-26.1'

        # Case 3. missing required options
        required = ['name', 'version', 'arch', 'target',
                    'indirection_template', 'results_loc']
        for r in required:
            orig = getattr(self.task_opts, r)
            setattr(self.task_opts, r, None)
            expected = "Missing the following required options: "
            expected += "--" + r.replace('_', '-') + "\n"
            with self.assertRaises(koji.GenericError) as cm:
                with  mock.patch('sys.stdout', new_callable=six.StringIO) as stdout:
                    _build_image_indirection(
                        self.options, self.task_opts, self.session, [])
            self.assert_console_message(stdout, expected)
            self.assertEqual(
                str(cm.exception), "Missing required options specified above")
            self.activate_session.assert_not_called()
            setattr(self.task_opts, r, orig)

        # Case 4. target not found error
        self.session.getBuildTarget.return_value = {}
        expected = "Unknown build target: %s" % {}
        with self.assertRaises(koji.GenericError) as cm:
            _build_image_indirection(
                self.options, self.task_opts, self.session, [])
        self.assertEqual(str(cm.exception), expected)
        self.activate_session.assert_called_with(self.session, self.options)

        # Case 5. tag not found error
        self.session.getBuildTarget.return_value = self.build_target
        self.session.getTag.return_value = {}
        expected = "Unknown destination tag: %s" % self.build_target['dest_tag_name']
        with self.assertRaises(koji.GenericError) as cm:
            _build_image_indirection(
                self.options, self.task_opts, self.session, [])
        self.assertEqual(str(cm.exception), expected)
        self.activate_session.assert_called_with(self.session, self.options)

        # Case 6. --indirection-template-url is not given and --scatch is not set
        self.session.getTag.return_value = self.dest_tag
        self.task_opts.indirection_template_url = None
        self.task_opts.scratch = None
        expected = "Non-scratch builds must provide a URL for the indirection template"
        with self.assertRaises(koji.GenericError) as cm:
            _build_image_indirection(
                self.options, self.task_opts, self.session, [])
        self.assertEqual(str(cm.exception), expected)
        self.activate_session.assert_called_with(self.session, self.options)


class TestImageBuildIndirection(utils.CliTestCase):

    # Show long diffs in error output...
    maxDiff = None

    def setUp(self):
        self.options = mock.MagicMock()
        self.session = mock.MagicMock()

        self.error_format = """Usage: %s image-build-indirection [base_image] [utility_image] [indirection_build_template]
       %s image-build --config <FILE>

(Specify the --help global option for a list of other help options)

%s: error: {message}
""" % (self.progname, self.progname, self.progname)

    @mock.patch('koji_cli.commands._build_image_indirection')
    def test_handle_image_build_indirection(self, build_image_mock):
        """Test handle_image_build_indirection function"""
        handle_image_build_indirection(self.options, self.session, [])
        args, kwargs = build_image_mock.call_args
        empty_opts = dict((k, None) for k in TASK_OPTIONS)
        self.assertDictEqual(empty_opts, args[1].__dict__)

    def test_handle_image_build_indirection_help(self):
        """Test handle_image_build_indirection help message"""
        self.assert_help(
            handle_image_build_indirection,
            """Usage: %s image-build-indirection [base_image] [utility_image] [indirection_build_template]
       %s image-build --config <FILE>

(Specify the --help global option for a list of other help options)

Options:
  -h, --help            show this help message and exit
  --config=CONFIG       Use a configuration file to define image-build options
                        instead of command line options (they will be
                        ignored).
  --background          Run the image creation task at a lower priority
  --name=NAME           Name of the output image
  --version=VERSION     Version of the output image
  --release=RELEASE     Release of the output image
  --arch=ARCH           Architecture of the output image and input images
  --target=TARGET       Build target to use for the indirection build
  --skip-tag            Do not tag the resulting build
  --base-image-task=BASE_IMAGE_TASK
                        ID of the createImage task of the base image to be
                        used
  --base-image-build=BASE_IMAGE_BUILD
                        NVR or build ID of the base image to be used
  --utility-image-task=UTILITY_IMAGE_TASK
                        ID of the createImage task of the utility image to be
                        used
  --utility-image-build=UTILITY_IMAGE_BUILD
                        NVR or build ID of the utility image to be used
  --indirection-template=INDIRECTION_TEMPLATE
                        Name of the local file, or SCM file containing the
                        template used to drive the indirection plugin
  --indirection-template-url=INDIRECTION_TEMPLATE_URL
                        SCM URL containing the template used to drive the
                        indirection plugin
  --results-loc=RESULTS_LOC
                        Relative path inside the working space image where the
                        results should be extracted from
  --scratch             Create a scratch image
  --wait                Wait on the image creation, even if running in the
                        background
  --noprogress          Do not display progress of the upload
""" % (self.progname, self.progname))


if __name__ == '__main__':
    unittest.main()
