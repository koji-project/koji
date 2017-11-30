PYMAJORVER := $(shell $(PYTHON) -c 'import sys; print(sys.version_info[0])')
PYVER := $(shell $(PYTHON) -c 'import sys; print("%.3s" %(sys.version))')
PYSYSDIR := $(shell $(PYTHON) -c 'import sys; print(sys.prefix)')
PYLIBDIR = $(PYSYSDIR)/lib/python$(PYVER)
PKGDIR = $(PYLIBDIR)/site-packages

CLIPLUGINDIR = $(PKGDIR)/koji_cli_plugins
HUBPLUGINDIR = /usr/lib/koji-hub-plugins
BUILDERPLUGINDIR = /usr/lib/koji-builder-plugins
CLIFILES = $(wildcard cli/*.py)
HUBFILES = $(wildcard hub/*.py)
BUILDERFILES = $(wildcard builder/*.py)
CLICONFDIR = /etc/koji/plugins
HUBCONFDIR = /etc/koji-hub/plugins
BUILDERCONFDIR = /etc/kojid/plugins
CLICONFFILES = $(wildcard cli/*.conf)
HUBCONFFILES = $(wildcard hub/*.conf)
BUILDERCONFFILES = $(wildcard builder/*.conf)

_default:
	@echo "nothing to make.  try make install"

clean:
	find . -name "__pycache__" -exec rm -rf {} \; ||:
	find . -name "*.pyc" -exec rm -f {} \;

install:
	@if [ "$(DESTDIR)" = "" ]; then \
		echo " "; \
		echo "ERROR: A destdir is required"; \
		exit 1; \
	fi

        ifndef KOJI_MINIMAL
		mkdir -p $(DESTDIR)/$(HUBPLUGINDIR);
		install -p -m 644 $(HUBFILES) $(DESTDIR)/$(HUBPLUGINDIR);
		$(PYTHON) -c "import compileall; compileall.compile_dir('$(DESTDIR)/$(HUBPLUGINDIR)', 1, '$(HUBPLUGINDIR)', 1)";
		mkdir -p $(DESTDIR)/$(HUBCONFDIR);
		install -p -m 644 $(HUBCONFFILES) $(DESTDIR)/$(HUBCONFDIR);
		mkdir -p $(DESTDIR)/$(BUILDERPLUGINDIR);
		install -p -m 644 $(BUILDERFILES) $(DESTDIR)/$(BUILDERPLUGINDIR);
		$(PYTHON) -c "import compileall; compileall.compile_dir('$(DESTDIR)/$(BUILDERPLUGINDIR)', 1, '$(BUILDERPLUGINDIR)', 1)";
		mkdir -p $(DESTDIR)/$(BUILDERCONFDIR);
		install -p -m 644 $(BUILDERCONFFILES) $(DESTDIR)/$(BUILDERCONFDIR);
        endif

	mkdir -p $(DESTDIR)/$(CLIPLUGINDIR)
	install -p -m 644 $(CLIFILES) $(DESTDIR)/$(CLIPLUGINDIR)
	$(PYTHON) -c "import compileall; compileall.compile_dir('$(DESTDIR)/$(CLIPLUGINDIR)', 1, '$(CLIPLUGINDIR)', 1)"
	mkdir -p $(DESTDIR)/$(CLICONFDIR)
        ifneq "$(CLICONFFILES)" ""
		install -p -m 644 $(CLICONFFILES) $(DESTDIR)/$(CLICONFDIR)
        endif
