SUBDIRS = kojiweb conf lib static

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

	mkdir -p $(DESTDIR)/usr/share/koji-web

	for d in $(SUBDIRS); do make DESTDIR=$(DESTDIR) \
		-C $$d install; [ $$? = 0 ] || exit 1; done
