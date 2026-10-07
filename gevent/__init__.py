# -*- coding: utf-8 -*-
"""
Pure-Python shim for gevent.
CHRLINE only uses gevent.monkey.patch_all() at import time.
This shim eliminates the need to compile heavy C-extensions on Android (Termux) and minimal containers.
"""
import time

def sleep(seconds=0):
    time.sleep(seconds)
