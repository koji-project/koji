FILES = koji

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

	mkdir -p $(DESTDIR)/usr/bin
	install -m 755 $(FILES) $(DESTDIR)/usr/bin
	install -m 644 koji.conf $(DESTDIR)/etc/koji.conf
