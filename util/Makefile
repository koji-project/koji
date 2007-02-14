BINFILES = kojira

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
	install -m 755 $(BINFILES) $(DESTDIR)/usr/sbin

	mkdir -p $(DESTDIR)/etc/rc.d/init.d
	install -m 755 kojira.init $(DESTDIR)/etc/rc.d/init.d/kojira

	mkdir -p $(DESTDIR)/etc/sysconfig
	install -m 644 kojira.sysconfig $(DESTDIR)/etc/sysconfig/kojira

	install -m 644 kojira.conf $(DESTDIR)/etc/kojira.conf
