SUBDIRS = kojiweb

SERVERDIR = /usr/share/koji-web/lib

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

	for d in $(SUBDIRS); do make DESTDIR=$(DESTDIR)/$(SERVERDIR) \
		-C $$d install; [ $$? = 0 ] || exit 1; done
