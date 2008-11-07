
PYTHON=python
SHAREDIR = $(DESTDIR)/usr/share/koji-builder
MODDIR = $(SHAREDIR)/lib
PYFILES = $(wildcard *.py)
PYVER := $(shell $(PYTHON) -c 'import sys; print "%.3s" %(sys.version)')

_default:
	@echo "nothing to make.  try make install"

clean:
	rm -f *.o *.so *.pyc *~

install:
	mkdir -p $(MODDIR)
	for p in $(PYFILES) ; do \
		install -p -m 644 $$p $(MODDIR)/$$p; \
	done
	$(PYTHON) -c "import compileall; compileall.compile_dir('$(MODDIR)', 1, '$(PYDIR)', 1)"

