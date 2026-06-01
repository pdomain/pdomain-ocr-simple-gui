import warnings


def test_hf_xet_dep_ignored():
    """Probe: this warning MUST be ignored by the filterwarnings config.
    With the old ':hf_xet' module filter, the test module != hf_xet so
    the ignore does NOT apply → pytest sees it as an ERROR → test FAILS.
    With the fixed (module-less) filter, it is ignored → test PASSES.
    """
    warnings.warn(
        "hf_xet.download_files() is deprecated. Use XetSession().new_file_download_group().start_download_file() instead.",
        DeprecationWarning,
        stacklevel=1,
    )
