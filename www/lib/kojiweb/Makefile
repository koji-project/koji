PACKAGE = $(shell basename `pwd`)
PYFILES = $(wildcard *.py)
PKGDIR = $(shell $(PYTHON) ../../devtools/get_site_packages.py )/$(PACKAGE)

SERVERDIR = /kojiweb
FILES = $(wildcard *.py *.html.j2)

_default:
	@echo "nothing to make.  try make install"

clean:
	rm -f *.o *.so *.pyc *~
	rm -rf __pycache__
	for d in $(SUBDIRS); do make -s -C $$d clean; done

install:
	@if [ "$(DESTDIR)" = "" ]; then \
		echo " "; \
		echo "ERROR: A destdir is required"; \
		exit 1; \
	fi

	mkdir -p $(DESTDIR)/$(SERVERDIR)
	for p in $(PYFILES) ; do \
		install -p -m 644 $$p $(DESTDIR)/$(SERVERDIR)/$$p; \
	done
	$(PYTHON) -c "import compileall; compileall.compile_dir('$(DESTDIR)/$(SERVERDIR)', 1, '$(PYDIR)', 1)"
