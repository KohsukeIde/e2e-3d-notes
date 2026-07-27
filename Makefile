PYTHON ?= python3

.PHONY: figures check

figures:
	$(PYTHON) scripts/make_figures.py
	$(PYTHON) scripts/make_recal3r_single_write_figures.py

check:
	$(PYTHON) -m py_compile scripts/make_figures.py
	$(PYTHON) -m py_compile scripts/make_recal3r_single_write_figures.py
	$(PYTHON) scripts/make_figures.py --check
	$(PYTHON) scripts/make_recal3r_single_write_figures.py --check
