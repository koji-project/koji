Unit tests in Fedora's Jenkins
==============================

We're using CentOS's `Jenkins
<https://jenkins-fedora-infra.apps.ocp.ci.centos.org/job/koji>`_ infrastructure
for automatically running unit tests for new commits in master branch.

Pagure triggers tests for any new pull request. It can be also triggered
manually by pressing "Rerun CI" button in PR.

Currently we run tests on Fedora 33/34/rawhide and CentOS 7/8 platforms.

Usage
-----

If you need any change in jenkins setup, please file a pagure issue. As part
of solving issue, this documentation must be updated to reflect current state
in jenkins.

Configuration
-------------

- Public access is for everyone with no need to log in to jenkins.
- Admin access is via same interface and currently tkopecek have
   access there. If you need access for yourself (you're probably part of
   brew/koji team) create ticket in https://pagure.io/centos-infra requesting this.
   Prerequisite for this is CentOS account.

- Setup - Following items are set-up via
   https://jenkins-fedora-infra.apps.ocp.ci.centos.org/job/koji/configure

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
- *Restrict where this project can be run* - F33 is the only used agent now.
    Basically we need an agent which supports podman as all the tests are run in
    docker images managed by podman.

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

- *Build* - most important part - script which runs tests itself. Basically we
  run tests in containers, last one also run flake8 and is used for coverage
  report.


.. code-block:: shell

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

    # centos:7
    rm -rf .tox
    podman run --rm --pull=always -v $PWD:/koji --security-opt label=disable --name koji-centos-test-7 quay.io/tkopecek/koji-centos-test:7 bash -c "cd /koji && tox -e py2"
    podman rmi quay.io/tkopecek/koji-centos-test:7

    # centos:8
    rm -rf .tox
    podman run --rm --pull=always -v $PWD:/koji --security-opt label=disable --name koji-centos-test-8 quay.io/tkopecek/koji-centos-test:8 bash -c "cd /koji && tox -e py3"
    podman rmi quay.io/tkopecek/koji-centos-test:8

    # fedora:32
    rm -rf .tox
    podman run --rm --pull=always -v $PWD:/koji --security-opt label=disable --name koji-fedora-test-32 quay.io/tkopecek/koji-fedora-test:32 bash -c "cd /koji && tox -e py3"
    podman rmi quay.io/tkopecek/koji-fedora-test:32

    # fedora:33
    rm -rf .tox
    podman run --rm --pull=always -v $PWD:/koji --security-opt label=disable --name koji-fedora-test-33 quay.io/tkopecek/koji-fedora-test:33 bash -c "cd /koji && tox -e py3"
    podman rmi quay.io/tkopecek/koji-fedora-test:33

    # fedora:rawhide
    rm -rf .tox
    podman run --rm --pull=always -v $PWD:/koji --security-opt label=disable --name koji-fedora-test-rawhide quay.io/tkopecek/koji-fedora-test:rawhide bash -c "cd /koji && tox -e flake8,py3"
    podman rmi quay.io/tkopecek/koji-fedora-test:rawhide

- *Post-build actions*

  * *Publish Cobertura Coverage report*: coverage.xml - this will create coverage report accessible via jenkins web ui
  * *Report Violations* - *pep8*: flake8_report.txt
  * *E-mail notification*:

    * Recipients: tkopecek@redhat.com exd-sp-rhel-build-alerts@redhat.com
    * Send separate e-mails to individuals who broke the build

- *Send messages to fedmsg*
