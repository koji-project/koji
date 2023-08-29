BUILDDIR      = build
SQLFILES = $(wildcard *.sql)
SQLDIR = /usr/share/koji

clean:
	rm -rf $(BUILDDIR)/*

install:
	@if [ "$(DESTDIR)" = "" ]; then \
		echo " "; \
		echo "ERROR: A destdir is required"; \
		exit 1; \
	fi

	mkdir -p $(DESTDIR)/$(SQLDIR)
	for p in $(SQLFILES) ; do \
		install -p -m 644 $$p $(DESTDIR)/$(SQLDIR)/$$p; \
	done
