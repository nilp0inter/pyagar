import pytest


def test_package_import():
    try:
        import pyagar
    except ImportError as exc:
        assert False, exc
    else:
        assert True
