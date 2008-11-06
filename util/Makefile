BINFILES = kojira koji-gc koji-shadow

_default:
	@echo "nothing to make. try make install"

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

	mkdir -p $(DESTDIR)/etc/rc.d/init.d
	install -p -m 755 kojira.init $(DESTDIR)/etc/rc.d/init.d/kojira

	mkdir -p $(DESTDIR)/etc/sysconfig
	install -p -m 644 kojira.sysconfig $(DESTDIR)/etc/sysconfig/kojira

	mkdir -p $(DESTDIR)/etc/kojira
	install -p -m 644 kojira.conf $(DESTDIR)/etc/kojira/kojira.conf

	mkdir -p $(DESTDIR)/etc/koji-gc
	install -p -m 644 koji-gc.conf $(DESTDIR)/etc/koji-gc/koji-gc.conf

	mkdir -p $(DESTDIR)/etc/koji-shadow
	install -p -m 644 koji-shadow.conf $(DESTDIR)/etc/koji-shadow/koji-shadow.conf
