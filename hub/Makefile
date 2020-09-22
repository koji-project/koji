PACKAGE = $(shell basename `pwd`)
PYFILES = $(wildcard *.py)
PKGDIR = $(shell $(PYTHON) -c "import site; print(site.getsitepackages()[0])")/$(PACKAGE)

SERVERDIR = /usr/share/koji-hub
PYFILES = $(wildcard *.py)

_default:
	@echo "nothing to make.  try make install"

clean:
	rm -f *.o *.so *.pyc *~
	rm -rf __pycache__

install:
	@if [ "$(DESTDIR)" = "" ]; then \
		echo " "; \
		echo "ERROR: A destdir is required"; \
		exit 1; \
	fi

	mkdir -p $(DESTDIR)/etc/httpd/conf.d
	install -p -m 644 httpd.conf $(DESTDIR)/etc/httpd/conf.d/kojihub.conf

	mkdir -p $(DESTDIR)/etc/koji-hub
	install -p -m 644 hub.conf $(DESTDIR)/etc/koji-hub/hub.conf
	mkdir -p $(DESTDIR)/etc/koji-hub/hub.conf.d

	mkdir -p $(DESTDIR)/$(SERVERDIR)
	for p in $(PYFILES) ; do \
		install -p -m 644 $$p $(DESTDIR)/$(SERVERDIR)/$$p; \
	done
	$(PYTHON) -c "import compileall; compileall.compile_dir('$(DESTDIR)/$(SERVERDIR)', 1, '$(PYDIR)', 1)"

