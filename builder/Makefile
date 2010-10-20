
BINFILES = kojid
LIBEXECFILES = mergerepos

_default:
	@echo "nothing to make.  try make install"

clean:
	rm -f *.o *.so *.pyc *~


install:
	@if [ "$(DESTDIR)" = "" ]; then \
		echo " "; \
		echo "ERROR: A destdir is required"; \
		exit 1; \
	fi

	mkdir -p $(DESTDIR)/usr/sbin
	install -p -m 755 $(BINFILES) $(DESTDIR)/usr/sbin

	mkdir -p $(DESTDIR)/usr/libexec/kojid
	install -p -m 755 $(LIBEXECFILES) $(DESTDIR)/usr/libexec/kojid

	mkdir -p $(DESTDIR)/etc/mock/koji
	mkdir -p $(DESTDIR)/etc/rc.d/init.d
	install -p -m 755 kojid.init $(DESTDIR)/etc/rc.d/init.d/kojid

	mkdir -p $(DESTDIR)/etc/sysconfig
	install -p -m 644 kojid.sysconfig $(DESTDIR)/etc/sysconfig/kojid

	mkdir -p $(DESTDIR)/etc/kojid
	install -p -m 644 kojid.conf $(DESTDIR)/etc/kojid/kojid.conf


