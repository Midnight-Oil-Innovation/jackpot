#!/usr/bin/env python3
"""scripts/srt_settings.py — emit srt sandbox settings for a worktree.

Usage: python scripts/srt_settings.py [worktree] > /tmp/srt.json
The domain list is the threat posture: inference, code host, and the package/vuln
sources the dependency gate needs. Nothing else.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ALLOWED_DOMAINS = [
    "api.anthropic.com",
    "github.com",
    "*.github.com",
    "api.github.com",
    "codeload.github.com",
    "api.osv.dev",
    "pypi.org",
    "files.pythonhosted.org",
]
DENY_READ = ["~/.ssh", "~/.aws", "~/.config/gcloud", "~/.kube"]


def main() -> int:
    root = Path(sys.argv[1] if len(sys.argv) > 1 else os.getcwd()).resolve()
    print(
        json.dumps(
            {
                "network": {"allowedDomains": ALLOWED_DOMAINS, "deniedDomains": []},
                "filesystem": {"allowWrite": [str(root)], "denyRead": DENY_READ},
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
