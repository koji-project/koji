PACKAGE = $(shell basename `pwd`)
PYFILES = $(wildcard *.py)
PKGDIR = $(shell $(PYTHON) -c "from distutils.sysconfig import get_python_lib; print(get_python_lib())")/$(PACKAGE)

SERVERDIR = /kojiweb
FILES = $(wildcard *.py *.chtml)

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
