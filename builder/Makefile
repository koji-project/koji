PYVER_MAJOR := $(shell $(PYTHON) -c 'import sys; print(".".join(sys.version.split(".")[:1]))')

BINFILES = kojid
LIBEXECFILES = mergerepos
SBINDIR ?= /usr/sbin
SYSTEMDSYSTEMUNITDIR = $(shell pkg-config systemd --variable=systemdsystemunitdir)

_default:
	@echo "nothing to make.  try make install"

clean:
	rm -f *.o *.so *.pyc *~ kojidc
	rm -rf __pycache__


_install:
	@if [ "$(DESTDIR)" = "" ]; then \
		echo " "; \
		echo "ERROR: A destdir is required"; \
		exit 1; \
	fi

	mkdir -p $(DESTDIR)$(SBINDIR)
	install -p -m 755 $(BINFILES) $(DESTDIR)$(SBINDIR)

	@if [ "$(PYVER_MAJOR)" -lt 3 ] ; then \
		mkdir -p $(DESTDIR)/usr/libexec/kojid; \
		install -p -m 755 $(LIBEXECFILES) $(DESTDIR)/usr/libexec/kojid; \
	fi

	mkdir -p $(DESTDIR)/etc/mock/koji

	mkdir -p $(DESTDIR)/etc/kojid
	install -p -m 644 kojid.conf $(DESTDIR)/etc/kojid/kojid.conf

install: _install
	mkdir -p $(DESTDIR)$(SYSTEMDSYSTEMUNITDIR)
	install -p -m 644 kojid.service $(DESTDIR)$(SYSTEMDSYSTEMUNITDIR)
