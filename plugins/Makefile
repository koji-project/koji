PYTHON=python
HUBPLUGINDIR = /usr/lib/koji-hub-plugins
BUILDERPLUGINDIR = /usr/lib/koji-builder-plugins
HUBFILES = $(wildcard hub/*.py)
BUILDERFILES = $(wildcard builder/*.py)
HUBCONFDIR = /etc/koji-hub/plugins
BUILDERCONFDIR = /etc/kojid/plugins
HUBCONFFILES = $(wildcard hub/*.conf)
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

	mkdir -p $(DESTDIR)/$(HUBPLUGINDIR)
	mkdir -p $(DESTDIR)/$(BUILDERPLUGINDIR)
	install -p -m 644 $(HUBFILES) $(DESTDIR)/$(HUBPLUGINDIR)
	install -p -m 644 $(BUILDERFILES) $(DESTDIR)/$(BUILDERPLUGINDIR)
	$(PYTHON) -c "import compileall; compileall.compile_dir('$(DESTDIR)/$(HUBPLUGINDIR)', 1, '$(HUBPLUGINDIR)', 1)"
	$(PYTHON) -c "import compileall; compileall.compile_dir('$(DESTDIR)/$(BUILDERPLUGINDIR)', 1, '$(BUILDERPLUGINDIR)', 1)"
	mkdir -p $(DESTDIR)/$(HUBCONFDIR)
	mkdir -p $(DESTDIR)/$(BUILDERCONFDIR)
	install -p -m 644 $(HUBCONFFILES) $(DESTDIR)/$(HUBCONFDIR)
	install -p -m 644 $(BUILDERCONFFILES) $(DESTDIR)/$(BUILDERCONFDIR)
