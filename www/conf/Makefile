_default:
	@echo "nothing to make.  try make install"

clean:
	rm -f *.o *.so *.pyc *~
	for d in $(SUBDIRS); do make -s -C $$d clean; done

install:
	@if [ "$(DESTDIR)" = "" ]; then \
		echo " "; \
		echo "ERROR: A destdir is required"; \
		exit 1; \
	fi

	mkdir -p $(DESTDIR)/etc/httpd/conf.d
	install -p -m 644 kojiweb.conf $(DESTDIR)/etc/httpd/conf.d/kojiweb.conf

	mkdir -p $(DESTDIR)/etc/kojiweb
	install -p -m 644 web.conf $(DESTDIR)/etc/kojiweb/web.conf
	mkdir -p $(DESTDIR)/etc/kojiweb/web.conf.d
