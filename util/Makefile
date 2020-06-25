BINFILES = kojira koji-gc koji-shadow koji-sweep-db koji-sidetag-cleanup
SYSTEMDSYSTEMUNITDIR = $(shell pkg-config systemd --variable=systemdsystemunitdir)
TYPE = systemd

_default:
	@echo "nothing to make. try make install"

clean:
	rm -f *.o *.so *.pyc *~
	rm -rf __pycache__
	for b in $(BINFILES); do rm -f $${b}c; done

_install:
	@if [ "$(DESTDIR)" = "" ]; then \
		echo " "; \
		echo "ERROR: A destdir is required"; \
		exit 1; \
	fi
	mkdir -p $(DESTDIR)/usr/sbin
	install -p -m 755 $(BINFILES) $(DESTDIR)/usr/sbin

	mkdir -p $(DESTDIR)/etc/kojira
	install -p -m 644 kojira.conf $(DESTDIR)/etc/kojira/kojira.conf

	mkdir -p $(DESTDIR)/etc/koji-gc
	install -p -m 644 koji-gc.conf $(DESTDIR)/etc/koji-gc/koji-gc.conf
	install -p -m 644 email.tpl $(DESTDIR)/etc/koji-gc/email.tpl

	mkdir -p $(DESTDIR)/etc/koji-shadow
	install -p -m 644 koji-shadow.conf $(DESTDIR)/etc/koji-shadow/koji-shadow.conf

install-systemd: _install
	mkdir -p $(DESTDIR)$(SYSTEMDSYSTEMUNITDIR)
	install -p -m 644 kojira.service $(DESTDIR)$(SYSTEMDSYSTEMUNITDIR)
	install -p -m 644 koji-gc.service $(DESTDIR)$(SYSTEMDSYSTEMUNITDIR)
	install -p -m 644 koji-gc.timer $(DESTDIR)$(SYSTEMDSYSTEMUNITDIR)
	install -p -m 644 koji-sweep-db.service $(DESTDIR)$(SYSTEMDSYSTEMUNITDIR)
	install -p -m 644 koji-sweep-db.timer $(DESTDIR)$(SYSTEMDSYSTEMUNITDIR)

install-sysv: _install
	# no more utils support for sysv
	true

install: install-$(TYPE)
