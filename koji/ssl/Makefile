FILES = $(wildcard *.py)

PYTHON=python

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

	mkdir -p $(DESTDIR)
	install -p -m 644 $(FILES) $(DESTDIR)

	$(PYTHON) -c "import compileall; compileall.compile_dir('$(DESTDIR)', 1, '$(PYDIR)', 1)"
