.DEFAULT_GOAL := ci

# During the shim phase build delegates to just: frontend-build, then
# uv build --sdist and uv build --wheel. Keep this contract visible until
# tests/test_packaging.py moves its task-definition assertion to just.
.PHONY: %
%:
	@AI="$(AI)" OUT="$(OUT)" REGEN_ROOT="$(REGEN_ROOT)" SHA="$(SHA)" \
	HF_LAYOUT_FORK="$(HF_LAYOUT_FORK)" BUMP="$(BUMP)" TEST="$(TEST)" \
	K="$(K)" PYTHON_VERSION="$(PYTHON_VERSION)" ARGS="$(ARGS)" just $@
