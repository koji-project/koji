PYTHON=python
PLUGINDIR = /usr/lib/koji-hub-plugins
FILES = $(wildcard *.py)
CONFDIR = /etc/koji-hub/plugins
CONFFILES = $(wildcard *.conf)

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
	install -p -m 644 $(FILES) $(DESTDIR)/$(PLUGINDIR)
	$(PYTHON) -c "import compileall; compileall.compile_dir('$(DESTDIR)/$(PLUGINDIR)', 1, '$(PLUGINDIR)', 1)"
	mkdir -p $(DESTDIR)/$(CONFDIR)
	install -p -m 644 $(CONFFILES) $(DESTDIR)/$(CONFDIR)
