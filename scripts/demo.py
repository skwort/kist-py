"""Launch kist with a temporary demo library."""

import os

from screenshot import create_demo_library

lib = create_demo_library()
print(f"Demo library: {lib}")
os.chdir(lib)
os.execvp("kist", ["kist"])
