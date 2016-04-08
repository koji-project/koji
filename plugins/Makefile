PYTHON=python
PLUGINDIR = /usr/lib/koji-hub-plugins
BUILDERPLUGINDIR = /usr/lib/koji-builder-plugins
FILES = $(wildcard hub/*.py)
BUILDERFILES = $(wildcard builder/*.py)
CONFDIR = /etc/koji-hub/plugins
BUILDERCONFDIR = /etc/kojid
CONFFILES = $(wildcard hub/*.conf)
BUILDERCONFFILES = $(wildcard builder/*.conf)

_default:
	@echo "nothing to make.  try make install"

clean:
	rm -f *.o *.so *.pyc *.pyo *~

install:
	@if [ "$(DESTDIR)" = "" ]; then \
		echo " "; \
		echo "ERROR: A destdir is required"; \
		exit 1; \
	fi

	mkdir -p $(DESTDIR)/$(PLUGINDIR)
	mkdir -p $(DESTDIR)/$(BUILDERPLUGINDIR)
	install -p -m 644 $(FILES) $(DESTDIR)/$(PLUGINDIR)
	install -p -m 644 $(BUILDERFILES) $(DESTDIR)/$(BUILDERPLUGINDIR)
	$(PYTHON) -c "import compileall; compileall.compile_dir('$(DESTDIR)/$(PLUGINDIR)', 1, '$(PLUGINDIR)', 1)"
	$(PYTHON) -c "import compileall; compileall.compile_dir('$(DESTDIR)/$(BUILDERPLUGINDIR)', 1, '$(BUILDERPLUGINDIR)', 1)"
	mkdir -p $(DESTDIR)/$(CONFDIR)
	mkdir -p $(DESTDIR)/$(BUILDERCONFDIR)
	install -p -m 644 $(CONFFILES) $(DESTDIR)/$(CONFDIR)
	install -p -m 644 $(BUILDERCONFFILES) $(DESTDIR)/$(BUILDERCONFDIR)
