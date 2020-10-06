BINFILES = kojivmd
SHAREFILES = kojikamid
SYSTEMDSYSTEMUNITDIR = $(shell pkg-config systemd --variable=systemdsystemunitdir)

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

install: _install
	mkdir -p $(DESTDIR)$(SYSTEMDSYSTEMUNITDIR)
	install -p -m 644 kojivmd.service $(DESTDIR)$(SYSTEMDSYSTEMUNITDIR)
