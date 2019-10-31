SUBDIRS=koji_cli

PACKAGE = $(shell basename `pwd`)
PYVER := $(shell $(PYTHON) -c 'import sys; print("%.3s" %(sys.version))')
PYSYSDIR := $(shell $(PYTHON) -c 'import sys; print(sys.prefix)')
PYLIBDIR = $(PYSYSDIR)/lib/python$(PYVER)
PKGDIR = $(PYLIBDIR)/site-packages

FILES = koji

_default:
	@echo "nothing to make.  try make install"

clean:
	rm -f *.o *.so *.pyc *~ kojic

install:
	@if [ "$(DESTDIR)" = "" ]; then \
		echo " "; \
		echo "ERROR: A destdir is required"; \
		exit 1; \
	fi

	for d in $(SUBDIRS); do make DESTDIR=$(DESTDIR) \
		-C $$d install; [ $$? = 0 ] || exit 1; done

	mkdir -p $(DESTDIR)/usr/bin
	install -p -m 755 $(FILES) $(DESTDIR)/usr/bin
	mkdir -p $(DESTDIR)/etc/koji.conf.d
	install -p -m 644 koji.conf $(DESTDIR)/etc/koji.conf
	install -p -m 644 koji.conf $(DESTDIR)/etc/koji.conf
