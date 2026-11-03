"""Use `uv run python -m studio_sandbox.manage ...` for sandbox-only commands."""

import os
import sys


def main():
    # In particular, do not let a command-line override point migrations at
    # the normal project's PostgreSQL database.
    if any(
        arg == "--settings" or arg.startswith("--settings=") for arg in sys.argv[1:]
    ):
        raise SystemExit("The studio sandbox does not accept a settings override.")
    if len(sys.argv) > 1 and sys.argv[1] == "runserver":
        addresses = [arg for arg in sys.argv[2:] if not arg.startswith("-")]
        if "--ipv6" in sys.argv or "-6" in sys.argv or len(addresses) > 1:
            raise SystemExit("The studio sandbox must bind to 127.0.0.1 only.")
        if addresses and not addresses[0].startswith("127.0.0.1:"):
            raise SystemExit("The studio sandbox must bind to 127.0.0.1 only.")
        if not addresses:
            sys.argv.append("127.0.0.1:8765")
    os.environ["DJANGO_SETTINGS_MODULE"] = "studio_sandbox.settings"
    from django.core.management import execute_from_command_line

    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()
