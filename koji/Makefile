SUBDIRS = ssl

PYTHON=python
PACKAGE = $(shell basename `pwd`)
PYFILES = $(wildcard *.py)
PYSCRIPTS = context.py
PYVER := $(shell $(PYTHON) -c 'import sys; print "%.3s" %(sys.version)')
PYSYSDIR := $(shell $(PYTHON) -c 'import sys; print sys.prefix')
PYLIBDIR = $(PYSYSDIR)/lib/python$(PYVER)
PKGDIR = $(PYLIBDIR)/site-packages/$(PACKAGE)

_default:
	@echo "nothing to make.  try make install"

clean:
	rm -f *.o *.so *.pyc *~
	for d in $(SUBDIRS); do make -s -C $$d clean; done

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
