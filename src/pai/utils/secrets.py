from __future__ import annotations
import os, sys, getpass, subprocess
from typing import Optional

try:
    import keyring  # uses macOS Keychain on Darwin
except Exception:
    keyring = None  # type: ignore

SERVICE = "openai"

def get_openai_api_key() -> Optional[str]:
    """
    Return the OpenAI API key from macOS Keychain, service 'openai'.
    Tries, in order:
      1) keyring.get_credential('openai', None)  -> first matching item
      2) keyring.get_password('openai', <common accounts>)
      3) `security find-generic-password -s openai -w`
      4) env var OPENAI_API_KEY
    """
    # 1) keyring credential lookup (works without knowing account on some backends)
    if keyring is not None and hasattr(keyring, "get_credential"):
        try:
            cred = keyring.get_credential(SERVICE, None)  # type: ignore[arg-type]
            if cred and getattr(cred, "password", None):
                return cred.password.strip()
        except Exception:
            pass

    # 2) try common account names if present
    if keyring is not None:
        for account in ("OPENAI_API_KEY", "default", "openai", getpass.getuser()):
            try:
                val = keyring.get_password(SERVICE, account)
                if val:
                    return val.strip()
            except Exception:
                pass

    # 3) macOS 'security' fallback (grabs first generic password for service=openai)
    if sys.platform == "darwin":
        try:
            proc = subprocess.run(
                ["security", "find-generic-password", "-s", SERVICE, "-w"],
                capture_output=True, text=True, check=False
            )
            if proc.returncode == 0 and proc.stdout.strip():
                return proc.stdout.strip()
        except Exception:
            pass

    # 4) environment fallback
    env = os.getenv("OPENAI_API_KEY")
    return env.strip() if env else None
