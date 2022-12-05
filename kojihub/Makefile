PYVER_MAJOR := $(shell $(PYTHON) -c 'import sys; print(".".join(sys.version.split(".")[:1]))')
PACKAGE = kojihub
PYFILES = $(wildcard *.py)
PKGDIR = $(shell $(PYTHON) -c "from distutils.sysconfig import get_python_lib; print(get_python_lib())")/$(PACKAGE)

SERVERDIR = /usr/share/koji-hub

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

        # python module
	mkdir -p $(DESTDIR)/$(PKGDIR)
	for p in $(PYFILES) ; do \
		install -p -m 644 $$p $(DESTDIR)/$(PKGDIR)/$$p; \
	done

	$(PYTHON) -c "import compileall; compileall.compile_dir('$(DESTDIR)/$(PKGDIR)', 1, '$(PYDIR)', 1)"

        # application files
	mkdir -p $(DESTDIR)/etc/httpd/conf.d
	install -p -m 644 app/httpd.conf $(DESTDIR)/etc/httpd/conf.d/kojihub.conf

	mkdir -p $(DESTDIR)/etc/koji-hub
	install -p -m 644 app/hub.conf $(DESTDIR)/etc/koji-hub/hub.conf
	mkdir -p $(DESTDIR)/etc/koji-hub/hub.conf.d


	mkdir -p $(DESTDIR)/$(SERVERDIR)
	install -p -m 644 app/kojiapp.py $(DESTDIR)/$(SERVERDIR)/kojiapp.py
	$(PYTHON) -c "import compileall; compileall.compile_dir('$(DESTDIR)/$(SERVERDIR)', 1, '$(PYDIR)', 1)"
