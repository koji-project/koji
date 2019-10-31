BINFILES = kojivmd
SHAREFILES = kojikamid
SYSTEMDSYSTEMUNITDIR = $(shell pkg-config systemd --variable=systemdsystemunitdir)
TYPE = systemd

_default:
	@echo "nothing to make.  try make install"

clean:
	rm -f *.o *.so *.pyc *~ kojikamid kojikamidc kojivmdc

kojikamid: kojikamid.py
	bash fix_kojikamid.sh >kojikamid

_install: kojikamid
	@if [ "$(DESTDIR)" = "" ]; then \
		echo " "; \
		echo "ERROR: A destdir is required"; \
		exit 1; \
	fi

	mkdir -p $(DESTDIR)/usr/sbin
	install -p -m 755 $(BINFILES) $(DESTDIR)/usr/sbin

	mkdir -p $(DESTDIR)/usr/share/kojivmd
	install -p -m 644 $(SHAREFILES) $(DESTDIR)/usr/share/kojivmd

	mkdir -p $(DESTDIR)/etc/kojivmd
	install -p -m 644 kojivmd.conf $(DESTDIR)/etc/kojivmd/kojivmd.conf

install-systemd: _install
	mkdir -p $(DESTDIR)$(SYSTEMDSYSTEMUNITDIR)
	install -p -m 644 kojivmd.service $(DESTDIR)$(SYSTEMDSYSTEMUNITDIR)

install-sysv: _install
	mkdir -p $(DESTDIR)/etc/rc.d/init.d
	install -p -m 755 kojivmd.init $(DESTDIR)/etc/rc.d/init.d/kojivmd

	mkdir -p $(DESTDIR)/etc/sysconfig
	install -p -m 644 kojivmd.sysconfig $(DESTDIR)/etc/sysconfig/kojivmd

install: install-$(TYPE)
