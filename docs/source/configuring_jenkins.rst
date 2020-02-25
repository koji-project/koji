Unit tests in Fedora's Jenkins
==============================

We're using Fedora's `Jenkins <https://jenkins.fedorainfracloud.org/job/koji>`_
infrastructure for automatically running unit tests for new commits in
master branch.

Current setup uses periodical checking of koji's git and when new commits are
seen, tests are run. Normal developer needn't to care about his workflow, but can
use it for his advantage as it can run tests for him with platforms he has no
access to. Currently are tests run on Fedora 24, Fedora 25 and CentOS 6
platforms.

Usage
-----

If you need any change in jenkins setup, please file a pagure issue. As part
of solving issue, this documentation must be updated to reflect current state
in jenkins.

If you want to run tests against specific repo (your or official branch), log
in to jenkins (via FAS unified login), navigate to `Build with parameters
<https://jenkins.fedorainfracloud.org/job/koji/build?delay=0sec>`_ and put
your repository url to ``REPO`` and name of branch to ``BRANCH``.
``BRANCH_TO`` could be left blank as it is default set to *master*. Pressing
``BUILD`` should give you link to running build in all supported
environments.


Configuration
-------------

- Public access is for everyone with no need to log in to jenkins.
- Admin access is via same interface and currently tkopecek and mikem have
   access there. If you need access for yourself (you're probably part of
   brew/koji team) create jira in BREW project requesting this.
   Prerequisite for this is Fedora account (probably same one you are using
   for work in pagure).

- Setup - Following items are set-up via
   https://jenkins.fedorainfracloud.org/job/koji/configure

- Please don't change access rules (*Enable project-based security*
   fields) unless you've a corresponding jira for that, so every change of
   access is tracked there.
- *Job notifications* - when jenkins job finishes, it will send some info to
   pagure. Such call will add a comment to PR. For this REST hook needs to
   be configured:

   * Format: JSON
   * Protocol: HTTP
   * Event: Job Finalized
   * URL: <url taken from koji pagure settings which will look similar to https://pagure.io/api/0/ci/jenkins//koji/<hash>/build-finished
   * Timeout: 30000
   * Log: 0

- *This build is parametrized* (checkbox set to true) - it allows jenkins
   to use other branches than master (especially for PRs). Three parameters
   are defined there:

   * REPO - The repository for the pull request.
   * BRANCH - The branch for the pull request.
   * BRANCH_TO - A branch into which the pull request should be merged.

- *Discard Old Builds*

   * Strategy: Rotation
   * Days to keep build: 20
   * Max # of builds to keep: empty

- *Disable build* - it could be used if a lot of failing build happens with
    no vision of early recovery - temporarily suspend jenkins jobs
- *Execute concurrent builds if necessary* - We currently have no need of this
- *Restrict where this project can be run* - Fedora 24 is used for now which means 'F24' value
- *Source Code Management*

  * Git
  * Repositories

    * Repository URL: https://pagure.io/koji.git
    * Credentials: none
    * Branches to build: origin/master

- *Build triggers*

  * *Trigger builds remotely*: true

    * Authentication tokens: <token from koji pagure settings>

  * *Poll SCM*:

    * Schedule: H/5 * * * *

- *Build* - most important part - script which runs tests itself. Here you can also add missing requirements which will get installed via pip (not via rpms from F24!)


.. code-block:: shell

  # setup virtual environment
  rm -rf kojienv
  if [ -x /usr/bin/python3 ] ; then
      python3 -m venv --system-site-packages kojienv
  else
      virtualenv --system-site-packages kojienv
  fi
  source kojienv/bin/activate

  # install python requirements via pip, you can also specify exact versions here
  if [ $NODE_NAME == "EL6" ] ; then
      pip install "psycopg2<2.7" "urllib3<1.24" "requests<2.20" "requests-mock<1.5" \
                  "Markdown<3.1" "mock<3.0.0" nose python-qpid-proton coverage \
                  python-multilib Cheetah --upgrade --ignore-installed
  else
      pip install pip packaging --upgrade --ignore-installed
      pip install setuptools --upgrade --ignore-installed
      pip install psycopg2 requests-mock nose python-qpid-proton mock coverage \
                  python-multilib flake8 --upgrade --ignore-installed
      if [ -x /usr/bin/python3 ] ; then
          pip install Cheetah3 nose-cover3 --upgrade --ignore-installed
      else
          pip install Cheetah --upgrade --ignore-installed
      fi
  fi


  # rehash package to be sure updated versions are used
  hash -r

  # merge PR into main repository
  if [ -n "$REPO" -a -n "$BRANCH" ]; then
      git config --global user.email "test@example.com"
      git config --global user.name "Tester"
      git remote rm proposed || true
      git remote add proposed "$REPO"
      git fetch proposed
      git checkout "origin/${BRANCH_TO:-master}"
      git merge --no-ff "proposed/$BRANCH" -m "Merge PR"
  fi

  # remove possible coverage output and run tests
  coverage erase
  PYTHONPATH=hub/.:plugins/hub/.:plugins/builder/.:cli/plugins/cli/.:cli/.:www/lib/. nosetests --with-coverage --cover-package .
  coverage xml --omit 'kojienv/*'

  # run additional tests if configured
  #pylint . > pylint_report.txt
  #pep8 . > pep8_report.txt

  if [ $NODE_NAME == "EL6" ] ; then
      # fake report, flake8 is not available for old python
      echo > flake8_report.txt
  else
      flake8 cli hub builder plugins koji util www vm devtools tests --output-file flake8_report.txt
  fi

  # kill virtual environment
  deactivate

- *Post-build actions*

  * *Publish Cobertura Coverage report*: coverage.xml - this will create coverage report accessible via jenkins web ui
  * *Report Violations* - *pep8*: flake8_report.txt
  * *E-mail notification*:

    * Recipients: tkopecek@redhat.com brew-devel@redhat.com
    * Send separate e-mails to individuals who broke the build

- *Send messages to fedmsg*
