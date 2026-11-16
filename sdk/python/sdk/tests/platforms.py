import sys

import pytest

windows_only = pytest.mark.skipif(sys.platform != "win32", reason="Windows only")
posix_only = pytest.mark.skipif(sys.platform == "win32", reason="POSIX only")
