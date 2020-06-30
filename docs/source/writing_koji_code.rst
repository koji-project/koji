=================
Writing Koji Code
=================

Getting Started Hacking on Koji
===============================


This page gives an overview of the Koji code and then describes what
needs to change if you want to add a new type of task. A new task could
be for a new content type, or assembling the results of multiple builds
together, or something else that helps your workflow. New contributors
to Koji should leave this page knowing where to begin and have enough
understanding of Koji's architecture to be able to estimate how much
work is still ahead of them.

Task Flow
=========

A task starts with a user submitting it with the Koji client, which is a
command line interface. This contacts the hub, an apache-based server
application. It leaves a row in the database that represents a "free"
task, one that has not been assigned to a builder. Periodically, the
builders asynchronously ping the hub asking if there are any tasks
available, and at some point one will be given the new task. The hub
marks this in the database, and the builder begins executing the task (a
build).

Upon completion, the builder uploads the results to the hub, including
logs, binaries, environment information, and whatever else the task
handler for the build dictated. The hub moves the results to a permanent
shared storage solution, and marks the task as completed (or failed).
During this whole time, the webUI can be used to check up on progress.
So the flow of work is:

::

    Client -> Hub -> Builder -> Hub

If you wanted to add a new build type or task that was tightly
integrated in Koji's data model, you would need to modify the CLI, Hub,
Builder, and WebUI at a minimum. Alternatively, you could do this with a
plugin, which is far simpler but less flexible.

Component Overview
==================

Koji is comprised of several components, this section goes into details
for each one, and what you potentially may need to change. Every
component is written in Python, so you will need to know that language
beyond a beginner level.

Koji-client
-----------

koji-client is a command line interface that provides many hooks into
Koji. It allows the user to query much of the data as well as perform
actions such as adding users and initiating build requests.

Option Handling
~~~~~~~~~~~~~~~

The code is in ``cli/koji``. It uses ``OptionParsers`` extensively with
interspersed arguments disabled. That means these two commands are not
interpreted the same:

::

    $ koji -u admin -p password tag-build some-tag --force some-build
    $ koji tag-build -u admin -p password some-tag --force some-build

The second one will generate an error, because -u and -p are not options
for tag-build, they must show up before that because they are global
options that can be used with any subcommand. There will be two
``OptionParsers`` used with each command. The first is used to pick up
arguments to ``koji`` itself, and the second for the subcommand
specified. When the first one executes (see ``get_options()``) it will
figure out the subcommand and come up with a function name based on it.

The convention is to prepend the word ``handle_`` before it, and change
all hyphens to underscores. If a command does not require an account
with Koji, the function handle will prepended with ``anon_handle_``
instead. The code will dynamically call the derived function handle
which is where the second ``OptionParser`` is used to parse the
remaining options. To have your code log into Koji (you're writing a
handle\_ function), use the ``activate_session`` function. All function
signatures in the client code will get a session object, which is your
interface to the hub.

Profiles
~~~~~~~~

It is possible to run the Koji client with different configuration
profiles so that you can interact with multiple Koji instances easily.
The ``--profile`` option to the Koji command itself enables this. You
should have a ``~/.koji/config`` already, if not just copy from
``/etc/koji.conf`` to get a start. The profile command accepts an
argument that matches a section in that config file. So if your config
file had this:

::

    [Fedora]
    authtype = ssl
    server = https://koji.fedoraproject.org/kojihub
    topdir = /mnt/koji
    weburl = https://koji.fedoraproject.org/koji
    #pkgurl = https://koji.fedoraproject.org/packages
    cert = ~/.fedora.cert
    ca = ~/.fedora-upload-ca.cert
    serverca = ~/.fedora-server-ca.cert

    [MyKoji]
    server = https://koji.mydomain.com/kojihub
    authtype = kerberos
    topdir = /mnt/koji
    weburl = https://koji.mydomain.com/koji
    topurl = https://download.mydomain.com/kojifiles

you could pass Fedora or MyKoji to --profile.

Creating Tasks
~~~~~~~~~~~~~~

Once options are processed and understood, a task needs to be created on
the hub so that a builder can come along and take it. This is
accomplished with the ``makeTask`` method (defined on the Hub, so call
it on the ``session`` object). The name of the task should match the
name given to the task handler in the builder, which is explained later
on.

Be sure to process the channel, priority, background, and watch/nowatch
parameters too, which should be available to most new tasks. They'll be
buried in the first argument to your handler function, which captures
the options passed to the base Koji command.

If the client needs to make locally-available artifacts (config files,
sources, kickstarts) accessible to the builder, it must be uploaded to
the hub. This is the case with uploading SRPMs or kickstarts. You can
easily upload this content with the ``session.uploadWrapper`` method.
You can create progress bars as necessary with this snippet:

::

    if _running_in_bg() or task_opts.noprogress:
      callback = None
    else:
      callback = _progress_callback
    serverdir = unique_path('cli-image')   # create a unique path on the hub
    session.uploadWrapper(somefile, serverdir, callback=callback)

Task Arguments
~~~~~~~~~~~~~~

If you define a new task for Koji, you'll want the task submission
output to have the options ordered usefully. This output is
automatically generated, but sometimes it does not capture the more
important arguments you want displayed.

::

    Created task 10001810
    Watching tasks (this may be safely interrupted)...
    10001810 thing (noarch): free
    10001810 thing (noarch): free -> closed
      0 free  0 open  1 done  0 failed

    10001810 thing (noarch) completed successfully

In this (fake) example, you can see that "noarch" is the only option
being displayed, but maybe you want something more than just the task
architecture displayed, like some other options that were passed in. You
can fix this behavior in ``koji/__init__.py`` in the \_taskLabel
function. Here you can define the string(s) to display when Koji
receives status on a task. That is the return value.

Using multicall
~~~~~~~~~~~~~~~

Koji supports a multicall feature where many calls are passed to the
server wrapped as a single call. This can reduce the overhead when a
large number of related calls need to be made.

The ``ClientSession`` class provides support for this and there are several
examples in the existing client code. Some examples in the cli include:
``edit-host``, ``add-pkg``, ``disable-host``, and ``list-hosts``.

There are two ways to use multicall.
The original modal method works within the ``ClientSession`` object and
prevents making other normal calls until the multicall is completed.
The newer method uses a separate ``MultiCallSession`` object and is much
more flexible.

**Using MultiCallSession**

Note: this feature was added in Koji version 1.18.

A ``MultiCallSession`` object is used to track an individual multicall attached
to a session.
To create one, you can simply call your session's ``multicall`` method.
Once created, the object can be used like a session, but calls are stored
rather than sent immediately.
The stored calls are executed by calling the ``call_all()`` method.

::

    m = session.multicall()
    for task_id in mylist:
        m.cancelTask(task_id)
    m.call_all()

This object can also be used as a context manager, so the following is
equivalent:

::

    with session.multicall() as m:
        for task_id in mylist:
            m.cancelTask(task_id)

Method calls to a ``MultiCallSession`` object return a ``VirtualCall`` object
that stands in for the result.
Once the multicall is executed, the result of each call can be accessed via
the ``result`` property of the ``VirtualCall`` object.
Accessing the ``result`` property before the call is executed will result in
an error.

::

    with session.multicall() as m:
        tags = [m.getTag(tag_id) for tag_id in mylist]
    for tag in tags:
        print(tag.result['name'])

There are two parameters affecting the behavior of the multicall.
If the ``strict`` parameter is set to True, the multicall will raise the first
error it encounters, if any.
If the ``batch`` parameter is set to a number greater than zero, the multicall
will spread the calls across multiple multicall batches of at most that number.
These parameters may be passed when the ``MultiCallSession`` is initialized,
or they may be passed to the ``call_all`` method.

::

    with session.multicall(strict=True, batch=500):
        builds = [m.getBuild(build_id) for build_id in mylist]


**Using ClientSession.multiCall**

Note: this approach is still supported, but we highly recommend using
``MultiCallSession`` as described above, unless you need to support Koji
versions prior to 1.18.

To use the feature, you first set the ``multicall`` attribute of the session
to ``True``. Once this is done, the session will not immediately process
further calls but will instead store their parameters for later. To tell the
session to process them, use the ``multiCall()`` method (note the
capitalization).

The ``multiCall()`` method returns a list of results, one for each call
in the multicall. Each result with either be:

1. the result of the call wrapped in a singleton list
2. a dictionary representing the error raised by the call

Here is a simple example from the koji-tools package:

::

    session.multicall = True
    for host in hosts:
        session.listChannels(hostID=host['id'])
    for host, [channels] in zip(hosts, session.multiCall(strict=True)):
        host['channels'] = channels

Note that when using multicall for informational calls, it is important
to keep track of which result is which. Here we use the existing hosts
list as a unifying index. Python's ``zip`` function is useful here.
Also note the unpacking of the singletons.

The ``multiCall()`` method supports a few options. Here is its signature:

::

    multiCall(strict=False, batch=None):

If the strict option is set to True, then this method will raise the
first error it encounters, if any.

If the batch option is set to a number greater than zero, the calls
will be spread across multiple multicall batches of at most this
number.

The hub processes multicalls in a *single database transaction*. Note that if
the ``batch`` option is used, then each batch is a separate multicall in the
api and therefore a separate transaction.


Koji-Hub
--------

koji-hub is the center of all Koji operations. It is an XML-RPC server
running under mod\_wsgi in Apache. koji-hub is passive in that it only
receives XML-RPC calls and relies upon the build daemons and other
components to initiate communication. koji-hub is the only component
that has direct access to the database and is one of the two components
that have write access to the file system. If you want to make changes
to the webUI (new pages or themes), you are looking in the wrong
section, there is a separate component for that.

Implementation Details
~~~~~~~~~~~~~~~~~~~~~~

The **hub/kojihub.py** file is where the server-side code lives. If you
need to fix any server problems or want to add any new tasks, you will
need to modify this file. Changes to the database schema will almost
certainly require code changes too. This file gets deployed to
**/usr/share/koji-hub/kojihub.py**, whenever you make changes to that
remember to restart **httpd**. Also there are cases where httpd looks
for an existing .pyc file and takes it as-is, instead of re-compiling it
when the code is changed.

In the code there are two large classes: **RootExports** and
**HostExports**. RootExports exposes methods using XMLRPC for any client
that connects to the server. The Koji CLI makes use of this quite a bit.
If you want to expose a new API to any remote system, add your code
here. The HostExports class does the same thing except it will ensure
the requests are only coming from builders. Attempting to use an API
exposed here with the CLI will fail. If your work requires the builders
to call a new API, you should implement it here. Any other function
defined in this file is inaccessible by remote hosts. It is generally a
good practice to have the exposed APIs do very little work, and pass off
control to internal functions to do the heavy lifting.

Database Interactions
~~~~~~~~~~~~~~~~~~~~~

Database interactions are done with raw query strings, not with any kind
of modern ORM. Consider using context objects from the Koji contexts
library for thread-safe interactions. The database schema is captured in
the **docs** directory in the root of a git clone. A visualization of
the schema is not available at the time of this writing.

If you plan to introduce schema changes, please update both
``schema.sql`` and provide a migration script if necessary.

Troubleshooting
~~~~~~~~~~~~~~~

The hub runs in an Apache service, so you will need to look in Apache
logs for error messages if you are encountering 500 errors or the
service is failing to start. Specifically you want to check in:

-  /var/log/httpd/error\_log
-  /var/log/httpd/ssl\_error\_log

If you need more specific tracebacks and debugging data, consider
changing the debugging setting in **/etc/koji-hub/hub.conf**. Be advised
the hub is very verbose with this setting on, your logs will take up
gigabytes of space within several days.

Kojid
-----

kojid is the build daemon that runs on each of the build machines. Its
primary responsibility is polling for incoming build requests and
handling them accordingly. Essentially kojid asks koji-hub for work.
Koji also has support for tasks other than building. Creating install
images is one example. kojid is responsible for handling these tasks as
well. kojid uses mock for building. It also creates a fresh buildroot
for every build. kojid is written in Python and communicates with
koji-hub via XML-RPC.

Implementation Details
~~~~~~~~~~~~~~~~~~~~~~

The daemon runs as a service on a host that is traditionally not the
same as the hub or webUI. This is a good security practice because the
service runs as root, and executes untrusted code to produce builds on a
regular basis. Keeping the Hub separate limits the damage a malicious
package can do to the build system as a whole. For the same reason, the
filesystem that the hub keeps built software on should be mounted
Read-Only on the build host. It should call APIs on the hub that are
exposed through the ``HostExports`` class in the hub code. Whenever the
builder accepts a task, it forks a process to carry out the build.

An initscript/unit-file is available for kojid, so it can be stopped and
started like a normal service. Remember to do this when you deploy
changes!

TaskHandlers
^^^^^^^^^^^^

All tasks in kojid have a ``TaskHandler`` class that defines what to do
when the task is picked up from the hub. The base class is defined in
``koji/tasks.py`` where a lot of useful utility methods are available.
An example is ``uploadFile``, which is used to upload logs and built
binaries from a completed build to the hub since the shared filesystem
is read only.

The daemon code lives in ``builder/kojid``, which is deployed to
/usr/sbin/kojid. In there you'll notice that each task handler class has
a ``Methods`` member and ``_taskWeight`` member. These must be defined,
and the former is used to match the name of a waiting task (on the hub)
with the task handler code to execute. Each task handler object must
have a ``handler`` method defined, which is the entry point for the
forked process when a builder accepts a task.

Tasks can have subtasks, which is a typical model when a build can be
run on multiple architectures. In this case, developers should write 2
task handlers: one handles the build for exact one architecture, and one
that assembles the results of those tasks into a single build, and sends
status information to the hub. You can think of the latter handler as
the parent task.

All task handler objects have a ``session`` object defined, which is the
interface to use for communications with the hub. So, parent tasks
should kick off child tasks using the session object's subtask method
(which is part of HostExports). It should then call ``self.wait`` with
``all=True`` to wait for the results of the child tasks.

Here's a stub of what a new build task might look like:

::

    class BuildThingTask(BaseTaskHandler):
      Methods = ['thing']
      _taskWeight = 0.5

      def handler(self, a, b, arches, options):
        subtasks = {}
        for arch in arches:
          subtasks[arch] = session.host.subtask(method='thingArch', a, b, arch)
        results = self.wait(subtasks.values(), all=True)
        # parse results and put rows in database
        # put files in their final resting place
        return 'Build successful'

    class BuildThingArchTask(BaseTaskHandler):
      Methods = ['thingArch']
      _taskWeight = 2.0

      def handler(self, a, b, arch):
        # do the build, capture results in a variable
        self.uploadFile('/path/to/some/log')
        self.uploadFile('/path/to/binary/file')
        return result

Source Control Managers
^^^^^^^^^^^^^^^^^^^^^^^

If you your build needs to check out code from a Source Control Manager
(SCM) such as git or subversion, you can use SCM objects defined in
``koji/daemon.py``. They take a specially formed URL as an argument to
the constructor. Here's an example use. The second line is important, it
makes sure the SCM is in the whitelist of SCMs allowed in
``/etc/kojid/kojid.conf``.

::

    scm = SCM(url)
    scm.assert_allowed(self.options.allowed_scms)
    directory = scm.checkout('/checkout/path', session, uploaddir, logfile)

Checking out takes 4 arguments: where to checkout, a session object
(which is how authentication is handled), a directory to upload the log
to, and a string representing the log file name. Using this method Koji
will checkout (or clone) a remote repository and upload a log of the
standard output to the task results.

Build Root Objects
^^^^^^^^^^^^^^^^^^

It is encouraged to build software in mock chroots if appropriate. That
way Koji can easily track precise details about the environment in which
the build was executed. In ``builder/kojid`` a BuildRoot class is
defined, which provides an interface to execute mock commands. Here's an
example of their use:

::

    broot = BuildRoot(self.session, self.options, build_tag, arch, self.id)

A session object, task options, and a build tag should be passed in
as-is. You should also specify the architecture and the task ID. If you
ever need to pass in specialized options to mock, look in the
ImageTask.makeImgBuildRoot method to see how they are defined and passed
in to the BuildRoot constructor.

Troubleshooting
~~~~~~~~~~~~~~~

The daemon writes a log file to ``/var/log/kojid.log``. Debugging output
can be turned on in ``/etc/kojid/kojid.conf``.

Koji-Web
--------

koji-web is a set of scripts that run in mod\_wsgi and use the Cheetah
templating engine to provide a web interface to Koji. It acts as a
client to koji-hub providing a visual interface to perform a limited
amount of administration. koji-web exposes a lot of information and also
provides a means for certain operations, such as cancelling builds.

The web pages are derived from Cheetah templates, the syntax of which
you can read up on
`here <http://cheetahtemplate.org/users_guide/>`__. These
templates are the ``chtml`` files sitting in ``www/kojiweb``. You'll
notice quickly that these templates are referencing variables, but where
do they come from?

The ``www/kojiweb/index.py`` file provides them. There are several
functions named after the templates they support, and in each one a
dictionary called ``values`` is populated. This is how data is gathered
about the task, build, archive, or whatever the page is about. Take your
time with ``taskinfo.chtml`` in particular, as the conditionals there
have gotten quite long. If you are adding a new task to Koji, you will
need to extend this at a minimum. A new type of build task would require
this, and possibly another that is specific to viewing the archived
information about the build. (taskinfo vs. buildinfo)

If your web page needs to display the contents of a list or dictionary,
use the ``$printMap`` function to help with that. It is often sensible
to define a function that easily prints options and values in a
dictionary. An example of this is in taskinfo.chtml.

::

    #def printOpts($opts)
      #if $opts
      <strong>Options:</strong><br/>
      $printMap($opts, '&nbsp;&nbsp;')
      #end if
    #end def

Finally, if you need to expand the drop-down menus of "method" types
when searching for tasks in the WebUI, you will need to add them to the
``_TASKS`` list in ``www/kojiweb/index.py``. Add values where
appropriate to ``_TOPLEVEL_TASKS`` and ``_PARENT_TASKS`` as well so that
parent-child relationships show up correctly too.

Remember whenever you update a template or index.py, you will need to
deploy and restart apache/httpd!

Troubleshooting
~~~~~~~~~~~~~~~

Like the hub, this component is backed by apache, so you should follow
the same techniques for debugging Koji-Web as
`Koji-Hub <#Troubleshooting>`__.

Kojira
------

kojira is a daemon that keeps the build root repodata updated. It is
responsible for removing redundant build roots and cleaning up after a
build request is completed.

Building and Deploying Changes
==============================

The root of the git clone for Koji code contains a ``Makefile`` that has
a few targets to make building and deployment a little easier. Among
them are:

-  tarball: create a bz2 tarball that could be consumed in an rpm build
-  rpm: create Koji rpms. The NVRs will be defined by the spec file,
   which is also in the same directory. The results will appear in a
   ``noarch`` directory.
-  test-rpm: like rpm, but append the Release field with a date and time
   stamp for easy upgrade-deployment

Writing Koji plugins
====================

.. toctree::
  :hidden:

  writing_a_plugin

There is a separate documentation page :doc:`writing_a_plugin`.

Submitting Changes
==================

To submit code changes for Koji, please file a pull request in Pagure.

https://pagure.io/koji/pull-requests

Here are some guidelines on producing preferable pull requests.

-  Each request should be a coherent whole, e.g. a single feature or bug fix.
   Please do not bundle a series of unrelated changes into a single PR
-  Pull requests in Pagure come from a branch in your personal fork of Koji
   (either in Pagure or a remote git repo). Please use an appropriately named
   branch for this. Do not use the master branch of your fork. Also, please
   be aware that Pagure will automatically update the pull request if you
   modify the source branch
-  Your branch should be based against the current HEAD of the target branch
-  Please adhere to `PEP8 <https://www.python.org/dev/peps/pep-0008/>`__.
   While much of the older code in Koji does not, we try to stick to it
   with new code
-  Code which is imported into CLI or needed for stand-alone API calls must
   run in both 2.6+ and 3.x python versions. We use the python-six library
   for compatibility. The affected files are:

     - ``cli/*``
     - ``koji/__init__.py``
     - ``koji/auth.py``
     - ``koji/tasks.py``
     - ``koji/util.py``
     - ``tests/test_lib/*``
     - ``tests/test_cli/*``

- Check, that unit tests are not broken. Simply run ``make test`` in main
  directory of your branch to check both python2/3 compatible-code. Or you can
  also use ``make test2`` or ``make test3`` target for each of them.

Note that the core development team for Koji is small, so it may take a few
days for someone to reply to your request.

Partial work
------------

Pull requests are for changes that are complete and ready for inclusion, but
sometimes you have partial work that you may want feedback on. Please don't
submit a PR before your code is complete.

The preferred way to request early feedback is to push your changes to a your
own koji fork and then send an email to
`koji-devel AT lists.fedorahosted.org <https://lists.fedorahosted.org/mailman/listinfo/koji-devel>`__
requesting review. This approach is one step short of a PR, making it easy to
upgrade to a PR once the changes are ready.

Unit Tests
==========

Koji comes with a small test suite, that you should always run when making
changes to the code. To do so, just run ``make test`` in your terminal.

You will need to install the following packages to actually run the tests.

 * ``glibc-langpack-en``
 * ``make``
 * ``python3-cheetah``
 * ``python3-coverage``
 * ``python3-dateutil``
 * ``python3-mock``
 * ``python3-multilib``
 * ``python3-nose``
 * ``python3-psycopg2``
 * ``python3-qpid-proton``
 * ``python3-requests``
 * ``python3-requests-kerberos``
 * ``python3-requests-mock``

Please note that it is currently not supported to use *virtualenv* when hacking
on Koji.

Unit tests are run automatically for any commit in master branch. We use
Fedora's jenkins instance for that. Details are given here: :doc:`Unit tests
in Fedora's Jenkins <configuring_jenkins>`.

Further testing
===============

Currently we automatically build two versions of rpms in Fedora's `Copr
<https://copr.fedorainfracloud.org/>`__. First one is simple "master" branch and
is available `here <https://copr.fedorainfracloud.org/coprs/tkopecek/koji/>`__.
These RPMs are early release candidates before we tag each final release. Second
one lives `here
<https://copr.fedorainfracloud.org/coprs/tkopecek/koji-testing/>`__ and contains
the "master" branch with all the in-progress pull requests that have
"testing-ready" flag. Both repos are built once per four hours if there are new
changes in pagure.

Code Style
==========

We are using ``flake8`` to check the code style. Please refer to ``.flake8`` to
find the PEP8 and extra rules we are following/ignoring.

You will need to install the packages below to run the check.

 * ``python-flake8``
 * ``python-flake8-import-order``
