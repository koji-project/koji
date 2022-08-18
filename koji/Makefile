PYVER_MAJOR := $(shell $(PYTHON) -c 'import sys; print(".".join(sys.version.split(".")[:1]))')
PACKAGE = $(shell basename `pwd`)
PYFILES = $(wildcard *.py)
PYSCRIPTS =
SUBDIRS =
PKGDIR = $(shell $(PYTHON) -c "from distutils.sysconfig import get_python_lib; print(get_python_lib())")/$(PACKAGE)

ifeq ($(PYVER_MAJOR),2)
	PYFILES=$(filter-out db.py,$(PYFILES))
else
	PYFILES=$(PYFILES)
endif

_default:
	@echo "nothing to make.  try make install"

clean:
	rm -f *.o *.so *.pyc *~
	rm -rf __pycache__

install:
	mkdir -p $(DESTDIR)/$(PKGDIR)
	for p in $(PYFILES) ; do \
		install -p -m 644 $$p $(DESTDIR)/$(PKGDIR)/$$p; \
	done
	for p in $(PYSCRIPTS) ; do \
		chmod 0755 $(DESTDIR)/$(PKGDIR)/$$p; \
	done
	$(PYTHON) -c "import compileall; compileall.compile_dir('$(DESTDIR)/$(PKGDIR)', 1, '$(PYDIR)', 1)"

	for d in $(SUBDIRS); do make DESTDIR=$(DESTDIR)/$(PKGDIR)/$$d \
		-C $$d install; [ $$? = 0 ] || exit 1; done
