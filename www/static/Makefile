SUBDIRS = images errors js

SERVERDIR = /usr/share/koji-web/static
FILES = $(wildcard *.css)

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

	mkdir -p $(DESTDIR)/$(SERVERDIR)
	install -p -m 644 $(FILES) $(DESTDIR)/$(SERVERDIR)

	for d in $(SUBDIRS); do make DESTDIR=$(DESTDIR)/$(SERVERDIR) \
		-C $$d install; [ $$? = 0 ] || exit 1; done
