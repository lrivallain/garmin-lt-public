#!/usr/bin/env python3
"""Simple healthcheck script that doesn't trigger full initialization."""
import urllib.request
import sys

try:
    # Just check if the app is responding
    response = urllib.request.urlopen('http://localhost:5000/', timeout=5)
    if response.status == 200:
        sys.exit(0)
    else:
        sys.exit(1)
except Exception as e:
    print(f"Health check failed: {e}", file=sys.stderr)
    sys.exit(1)
