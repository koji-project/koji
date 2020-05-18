NAME=koji
SPECFILE = $(firstword $(wildcard *.spec))
SUBDIRS = hub builder koji cli util www plugins vm

ifndef PYTHON
export PYTHON=python2
endif

ifdef DIST
DIST_DEFINES := --define "dist $(DIST)"
endif

ifndef VERSION
VERSION := $(shell rpm $(RPM_DEFINES) $(DIST_DEFINES) -q --qf "%{VERSION}\n" --specfile $(SPECFILE)| head -1)
endif
# the release of the package
ifndef RELEASE
RELEASE := $(shell rpm $(RPM_DEFINES) $(DIST_DEFINES) -q --qf "%{RELEASE}\n" --specfile $(SPECFILE)| head -1)
endif

ifndef WORKDIR
WORKDIR := $(shell pwd)
endif
## Override RPM_WITH_DIRS to avoid the usage of these variables.
ifndef SRCRPMDIR
SRCRPMDIR = $(WORKDIR)
endif
ifndef BUILDDIR
BUILDDIR = $(WORKDIR)
endif
ifndef RPMDIR
RPMDIR = $(WORKDIR)
endif
## SOURCEDIR is special; it has to match the CVS checkout directory,-
## because the CVS checkout directory contains the patch files. So it basically-
## can't be overridden without breaking things. But we leave it a variable
## for consistency, and in hopes of convincing it to work sometime.
ifndef SOURCEDIR
SOURCEDIR := $(shell pwd)
endif


# RPM with all the overrides in place;
ifndef RPM
RPM := $(shell if test -f /usr/bin/rpmbuild ; then echo rpmbuild ; else echo rpm ; fi)
endif
ifndef RPM_WITH_DIRS
RPM_WITH_DIRS = $(RPM) --define "_sourcedir $(SOURCEDIR)" \
		    --define "_builddir $(BUILDDIR)" \
		    --define "_srcrpmdir $(SRCRPMDIR)" \
		    --define "_rpmdir $(RPMDIR)"
endif

# tag to export, defaulting to current tag in the spec file
ifndef TAG
TAG=$(NAME)-$(VERSION)-$(RELEASE)
endif

_default:
	@echo "read the makefile"

clean:
	rm -f *.o *.so *.pyc *~ koji*.bz2 koji*.src.rpm
	rm -rf __pycache__
	rm -rf devtools/fakehubc devtools/fakewebc devtools/__pycache__
	rm -rf koji-$(VERSION)
	for d in $(SUBDIRS); do make -s -C $$d clean; done
	find ./tests -name "__pycache__" -exec rm -rf {} \; ||:
	find ./tests -name "*.pyc" -exec rm -f {} \;
	rm -rf docs/source/__pycache__ docs/source/*.pyc
	coverage2 erase ||:
	coverage3 erase --rcfile .coveragerc3 ||:
	rm -rf htmlcov

git-clean:
	@git clean -d -q -x

test: test2 test3
	@echo "All tests are finished for python 2&3"

test2:
	coverage2 erase
	PYTHONPATH=.:plugins/builder/.:plugins/cli/.:cli/.:www/lib coverage2 run \
	    --source . -m nose tests/test_builder tests/test_cli tests/test_lib \
	    tests/test_plugins/test*builder.py tests/test_plugins/test*cli.py
	coverage2 report
	coverage2 html
	@echo Full coverage report at file://${CURDIR}/htmlcov/py2/index.html

test3:
	coverage3 erase --rcfile .coveragerc3
	PYTHONPATH=hub/.:plugins/hub/.:plugins/builder/.:plugins/cli/.:cli/.:www/lib coverage3 run \
	    --rcfile .coveragerc3 --source . -m nose
	coverage3 report --rcfile .coveragerc3
	coverage3 html --rcfile .coveragerc3
	@echo Full coverage report at file://${CURDIR}/htmlcov/py3/index.html

test-tarball:
	@rm -rf .koji-$(VERSION)
	@mkdir .koji-$(VERSION)
	@cp -al [A-Za-z]* .koji-$(VERSION)
	@mv .koji-$(VERSION) koji-$(VERSION)
	tar --bzip2 --exclude '*.tar.bz2' --exclude '*.rpm' --exclude '.#*' \
	    -cpf koji-$(VERSION).tar.bz2 koji-$(VERSION)
	@rm -rf koji-$(VERSION)

tarball: clean
	@git archive --format=tar --prefix=$(NAME)-$(VERSION)/ HEAD |bzip2 > $(NAME)-$(VERSION).tar.bz2

sources: tarball

srpm: tarball
	$(RPM_WITH_DIRS) $(DIST_DEFINES) -bs $(SPECFILE)

rpm: tarball
	$(RPM_WITH_DIRS) $(DIST_DEFINES) -bb $(SPECFILE)

test-rpm: tarball
	$(RPM_WITH_DIRS) $(DIST_DEFINES) --define "testbuild 1" -bb $(SPECFILE)

pypi:
	rm -rf dist
	python setup.py sdist
	# py2
	virtualenv -p /usr/bin/python2 build_py2
	build_py2/bin/pip install --upgrade pip setuptools wheel virtualenv
	build_py2/bin/python setup.py bdist_wheel
	rm -rf build_py2
	# py3
	python3 -m venv build_py3
	build_py3/bin/pip install --upgrade pip setuptools wheel virtualenv
	build_py3/bin/python setup.py bdist_wheel
	rm -rf build_py3

pypi-upload:
	twine upload dist/*

flake8:
	flake8

tag::
	git tag -a $(TAG)
	@echo "Tagged with: $(TAG)"
	@echo

force-tag::
	git tag -f -a $(TAG)
	@echo "Tagged with: $(TAG)"
	@echo

# If and only if "make build" fails, use "make force-tag" to 
# re-tag the version.
#force-tag: $(SPECFILE)
#	@$(MAKE) tag TAG_OPTS="-F $(TAG_OPTS)"

DESTDIR ?= /
TYPE = systemd
install:
	@if [ "$(DESTDIR)" = "" ]; then \
		echo " "; \
		echo "ERROR: A destdir is required"; \
		exit 1; \
	fi

	mkdir -p $(DESTDIR)

	for d in $(SUBDIRS); do make DESTDIR=`cd $(DESTDIR); pwd` \
		-C $$d install TYPE=$(TYPE); [ $$? = 0 ] || exit 1; done
