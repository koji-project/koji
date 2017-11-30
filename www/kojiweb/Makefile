SUBDIRS = includes

SERVERDIR = /usr/share/koji-web/scripts
FILES = $(wildcard *.py *.chtml)

_default:
	@echo "nothing to make.  try make install"

clean:
	rm -f *.o *.so *.pyc *~
	rm -rf __pycache__
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
