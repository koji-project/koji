SERVERDIR = /images
FILES = $(wildcard *.gif *.png *.ico *.svg)

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

	mkdir -p $(DESTDIR)/$(SERVERDIR)
	install -p -m 644 $(FILES) $(DESTDIR)/$(SERVERDIR)
