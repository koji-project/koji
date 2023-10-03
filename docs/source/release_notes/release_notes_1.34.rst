
Koji 1.34.0 Release notes
=========================

All changes can be found in `the roadmap <https://pagure.io/koji/roadmap/1.34/>`_.
Most important changes are listed here.

Check at least :ref:`scheduler <scheduler>` and :ref:`draft builds <draft-builds>` as the crucial changes
in this release.


Migrating from Koji 1.33/1.33.1
-------------------------------

For details on migrating see :doc:`../migrations/migrating_to_1.34`


Security Fixes
--------------

None


Client Changes
--------------
**Fix [still active] display for edit entries**

Not all active settings were correctly marked in ``list-history`` output.

| PR: https://pagure.io/koji/pull-request/3813

**Streamline python/json options in call command**

| PR: https://pagure.io/koji/pull-request/3846

Coherent usage of ``--json/--json-input/--json-output`` options.

**Handle hub w/o getKojiVersion in cancel tasks**

| PR: https://pagure.io/koji/pull-request/3889

Don't fail ``cancel`` command when used against old koji server.

**Fix wait-repo message when missing builds**

| PR: https://pagure.io/koji/pull-request/3915

Clarify message.

**list-permissions: backward compatibility for getUserPermsInheritance call**

| PR: https://pagure.io/koji/pull-request/3960

**Read config file on image build indirection**

| PR: https://pagure.io/koji/pull-request/3929

Option ``--config`` was already there, but it was doing nothing. Now, user
can pass all the options via config file similarly to the "classical" image build.

API Changes
-----------
**Unify getSessionInfo output**

| PR: https://pagure.io/koji/pull-request/3794
| PR: https://pagure.io/koji/pull-request/3927

Different fields were returned when ``getSessionInfo`` was called with
``details=True``. Now, same base fields are returned in both cases.

**Remove koji.AUTHTYPE_* in 1.34**

| PR: https://pagure.io/koji/pull-request/3818

These constants were deprecated while ago, use ``koji.AUTHTYPES`` enum instead.

**Extend getUser to get user groups**

| PR: https://pagure.io/koji/pull-request/3855

Additional ``groups`` option to get info about user's group membership.


**Short option for watch-logs --follow**

| PR: https://pagure.io/koji/pull-request/3884

Added `-f` as an alias for `--follow`.


System Changes
--------------
.. _scheduler:

**Scheduler part 1**

| PR: https://pagure.io/koji/pull-request/3772

Biggest change in this release. We're rewriting scheduler to allow better
utilization of builders and to have better control about what is built where
and when. This is the first part of the changes and it moves scheduling
responsibilities from builder to hub and unified queue.

This phase is transparent to administrators and users (even older builders are
provided "fake" API, so they can benefit from new hub code without noticing).
Two new CLI commands ``scheduler-info`` and ``scheduler-logs`` can be used to
gain insights to scheduler state.

Also there are some new options for hub to modify scheduler behaviour and
``koji-sweep-db`` is updated, so it can clean old scheduler logs.

In the next phase there should be added multi-target policies, concept of
builder resources, etc. which would allow fine-tuning of build requests. Crude
channels' logic then could be replaced by scheduler hints and hard limits for
selecting right builder.
  
**Remove get_sequence_value in 1.34**

| PR: https://pagure.io/koji/pull-request/3817

Deprecated ``get_sequence_value`` was finally removed. This could be of some
interest to plugin developers.

**Add support for sw_64 and loongarch64**

| PR: https://pagure.io/koji/pull-request/3836

Simple extension to support these architectures.

**Don't spawn createrepo if not needed**

| PR: https://pagure.io/koji/pull-request/3842

Performance improvement in some cases where it is not needed to rerun
createrepo when creating new tag (typically sidetag or some build tag which
doesn't modify its inherited content). Simple copy of the original repodata is
correct here.

**Package migration scripts to koji-hub**

| PR: https://pagure.io/koji/pull-request/3843
| PR: https://pagure.io/koji/pull-request/3920

Previously, these scripts were packaged with basic lib. It doesn't make much
sense, so they were moved to hub subpackage. You can find them now in
``/usr/share/koji`` there.

**Inherit group permissions**

| PR: https://pagure.io/koji/pull-request/3850

Intuitive understanding of group membership is to inherit everything what is
accessible via group inheritance.

**Fix user_in_group policy test**

| PR: https://pagure.io/koji/pull-request/3859

Bugfix of regression.

**Disable use_bootstrap_image if not requested**

| PR: https://pagure.io/koji/pull-request/3873

Mock's default behaviour changed to have this setting on by default. So, we've
extended our flag to allow also disabling this.

**new_build: build in error should be the old one**

| PR: https://pagure.io/koji/pull-request/3895

Error message was fixed to show correct data.

.. _draft-builds:

**Draft builds**

| PR: https://pagure.io/koji/pull-request/3913

Another big change in this release. Builds (rpm for now) can be run with
``--draft`` option. It is different from scratch build in the way that it is
1st class build with modified release (containing "-draft-<id>" suffix).
Nevertheless, this release change is done only on build level. RPMs are using
original release, so they are indistunguishible from other draft builds for
same NVR. Such behaviour violates rules that there are no two rpms with the
same filename. That is the reason, why they are called "draft builds".

To bring them back to uniqueness, such build can be "promoted". In such case it
is renamed to original release and all other draft builds from given NVR are
forever forbidden to be promoted.

Typical use would be PR/MR workflow. There could be many "candidate" draft
builds and only one which will pass testing and/or other workflows will be
promoted in the end as "real" build which can be used for distribution.

Handling of when/where draft builds can be used (e.g. in some buildroots but
not in the others) is done by ``is_draft`` policy test.

Draft builds could be viewed as "light namespacing" in koji or "more persistent
scratch builds".

**Retrieve task_id for older OSBS builds**

| PR: https://pagure.io/koji/pull-request/3897

It is hidden for regular usecases, but improves policy behaviour, e.g. that
`volume` policy can handle builds based on CG, etc.

**Raise an error on missing build directory (setBuildVolume)**

| PR: https://pagure.io/koji/pull-request/3886

Better error reporting in case of missing build directories.

**More general CG import logging**

| PR: https://pagure.io/koji/pull-request/3905

Fixes race condition when creating CG log.

**queryOpts for queryHistory**

| PR: https://pagure.io/koji/pull-request/3902

Adding support for standard ``queryOpts`` to this call.

**fix task_id extraction for missing extra**

| PR: https://pagure.io/koji/pull-request/3935

OSBS task now pass correct task data to volume policy

Builder Changes
---------------
**Switch to WatchedFileHandler for logger**

| PR: https://pagure.io/koji/pull-request/3537

Logrotate sometimes caused that kojid/kojira output was appended to already
rotated (even deleted) file. Change to ``WatchedFileHandler`` will ensure that
correct file is used.

**Wait with writing timestamps after results dir is created**

| PR: https://pagure.io/koji/pull-request/3834

``log_timestamps`` feature in some cases tried to write logs into directory
which hasn't existed yet causing build to fail from unrelated reasons.

**distrepo will not skip rpm stat by default**

| PR: https://pagure.io/koji/pull-request/3838

Reusing repodata with distrepo is dangerous as rpms could be signed with
different keys. So, now is the default behaviour to always stat rpms to be sure
that they don't differ from cached metadata. This behaviour can be overriden by
``--skip-stat`` CLI option. Note, that you've to be sure what you're doing in
such case (typically you don't care about signatures in this repo).

**Clean rpm db directory of broken symlinks**

| PR: https://pagure.io/koji/pull-request/3893

(At least) Fedora is moving rpm database directory. We've previously checked
existence of ``.migrated`` file but it is not enough in some transient
environments. Host rpm and buildroot rpm could handle these directories
differently resulting in bogus files preventing one of these to work. So, this
"hack" is cleaning up potentially broken files.


Kojira
------
**kojira no_repo_effective_age setting**

| PR: https://pagure.io/koji/pull-request/3830

New build tags (without repos) were not prioritized by kojira in best way.
Kojira assumed that this tag was never used, so it had very low priority. New
setting allows to set default "last use" value to improve the situation.


Web UI
------
**Better handling of deleted tags in kojiweb**

| PR: https://pagure.io/koji/pull-request/3828

Display deleted tags properly on all web pages.

**Fix duplicate build link on CG taskinfo page**

| PR: https://pagure.io/koji/pull-request/3857

Multiple ways how to store CG's ``task_id`` led to situation when task was
displayed twice.

**Display two decimal points for the task load in hosts page**

| PRL https://pagure.io/koji/pull-request/3911

Some floats were too long, stripped to two digits.

**Sort channels on hosts page**

| PR: https://pagure.io/koji/pull-request/3894

More readability in selectors.

Plugins
-------
**create initial repo for sidetag**

| PR: https://pagure.io/koji/pull-request/3841

``trigger_new_repo`` is new setting for sidetag plugin. When it is set to true,
it will trigger ``newRepo`` task as part of new sidetag creation. If it is not
set, old way (leave it on kojira) is used.

**sidetag: extend is_sidetag_owner for untag ops**

| PR: https://pagure.io/koji/pull-request/3851

``is_sidetag_owner`` policy has now ``tag/fromtag/both`` optional keywords for
tag specification.

**kiwi: Sort image rpm components before inserting**

| PR: https://pagure.io/koji/pull-request/3882

There is a potential db deadlock which is avoided by this reordering.


Documentation
-------------
**Fix docstring getTaskInfo**

| PR: https://pagure.io/koji/pull-request/3726

**More XMLRPC-related docs**

| PR: https://pagure.io/koji/pull-request/3761

**Fix release notes version**

| PR: https://pagure.io/koji/pull-request/3832

**Explain _ord() method**

| PR: https://pagure.io/koji/pull-request/3835

**readTaggedRPMS/Builds API documentation**

| PR: https://pagure.io/koji/pull-request/3840

**Fix param in createImageBuild docstring**

| PR: https://pagure.io/koji/pull-request/3876

**Example of how to enable a module via mock.module_setup_commands**

| PR: https://pagure.io/koji/pull-request/3879

**Update docstring for listPackages**

| PR: https://pagure.io/koji/pull-request/3904

**Fix return type (chainBuild)**

| PR: https://pagure.io/koji/pull-request/3924

Devtools and tests
------------------
**Basic vim syntax highlighting for hub policy**

| PR: https://pagure.io/koji/pull-request/3839

It can be used for editing hub policies. As it has no rigorous syntax it
doesn't work in 100%.

**Tox: Don't install coverage every run**

| PR: https://pagure.io/koji/pull-request/3861

A bit of performance improvement for running tests.

**Fix tests/flake8**

| PR: https://pagure.io/koji/pull-request/3865
| PR: https://pagure.io/koji/pull-request/3917

**Update Containerfiles**

| PR: https://pagure.io/koji/pull-request/3898

Updated to current Fedoras
