SERVERDIR = /js
FILES = $(wildcard *.js)

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

	cp -r jsolait $(DESTDIR)/$(SERVERDIR)
