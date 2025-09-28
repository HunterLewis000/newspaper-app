"""WSGI entrypoint that performs gevent monkey-patching before importing the
application. This ensures ssl and networking modules are patched early and
prevents MonkeyPatchWarning / RecursionError caused by late patching.
"""
from gevent import monkey
# Patch early, before other modules (requests, urllib3, botocore, ssl) are
# imported. Keep this file minimal — it should only patch and import the app.
monkey.patch_all()

from app import app  # noqa: E402


__all__ = ["app"]
