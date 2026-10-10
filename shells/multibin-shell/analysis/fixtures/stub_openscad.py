"""A stand-in for OpenSCAD, so gate_test.py can test compare.render without it.

It accepts OpenSCAD's arguments and does three things:
  - writes them, as a JSON list, beside the output file as OUTPUT.args.json;
  - writes the output file, unless the environment variable STUB_WRITE is 0;
  - prints the contents of the file named by STUB_CONSOLE, if set, to standard
    error, which is where OpenSCAD prints its messages.
"""

import json
import os
import sys


def main():
    args = sys.argv[1:]
    out = args[args.index("-o") + 1]
    with open(out + ".args.json", "w", encoding="utf-8") as f:
        json.dump(args, f)
    if os.environ.get("STUB_WRITE", "1") != "0":
        with open(out, "w", encoding="utf-8") as f:
            f.write("stub output")
    console = os.environ.get("STUB_CONSOLE")
    if console:
        with open(console, encoding="utf-8") as f:
            sys.stderr.write(f.read())


if __name__ == "__main__":
    main()
