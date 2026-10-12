"""A stand-in for OpenSCAD, so gate_test.py can test the render steps without it.

Called with --version, it prints a version line to standard error, as
OpenSCAD does. Otherwise it accepts OpenSCAD's arguments and does four things:
  - writes them, as a JSON list, beside the output file as OUTPUT.args.json;
  - writes the output file, unless the environment variable STUB_WRITE is 0;
  - writes the bytes of the file named by STUB_CONSOLE, if set, to standard
    error, which is where OpenSCAD prints its messages, unchanged;
  - writes the bytes of the file named by STUB_STDOUT, if set, to standard
    output, unchanged.
"""

import json
import os
import sys


def main():
    args = sys.argv[1:]
    if "--version" in args:
        sys.stderr.write("OpenSCAD version 0.0 (stand-in)\n")
        return
    out = args[args.index("-o") + 1]
    with open(out + ".args.json", "w", encoding="utf-8") as f:
        json.dump(args, f)
    if os.environ.get("STUB_WRITE", "1") != "0":
        with open(out, "w", encoding="utf-8") as f:
            f.write("stub output")
    for name, stream in (("STUB_CONSOLE", sys.stderr), ("STUB_STDOUT", sys.stdout)):
        if os.environ.get(name):
            with open(os.environ[name], "rb") as f:
                stream.buffer.write(f.read())
            stream.flush()


if __name__ == "__main__":
    main()
