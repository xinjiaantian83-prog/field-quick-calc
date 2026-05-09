import os
import sys
import tempfile


def _user_path(name):
    try:
        return os.path.join(os.path.expanduser("~"), name)
    except Exception:
        return name


try:
    numba_cache = os.environ.get("NUMBA_CACHE_DIR") or _user_path(".spriteanchor_numba_cache")
    try:
        os.makedirs(numba_cache, exist_ok=True)
    except Exception:
        numba_cache = os.path.join(tempfile.gettempdir(), "SpriteAnchor_numba_cache")
        os.makedirs(numba_cache, exist_ok=True)
    os.environ["NUMBA_CACHE_DIR"] = numba_cache
except Exception:
    pass

if not os.environ.get("U2NET_HOME"):
    candidates = []
    base = getattr(sys, "_MEIPASS", "")
    if base:
        candidates.append(os.path.join(base, "u2net"))
        candidates.append(os.path.join(os.path.dirname(base), "Resources", "u2net"))

    exe_dir = os.path.dirname(sys.executable)
    candidates.append(os.path.join(exe_dir, "..", "Resources", "u2net"))
    candidates.append(os.path.join(exe_dir, "u2net"))

    for path in candidates:
        path = os.path.abspath(path)
        if os.path.exists(os.path.join(path, "u2net.onnx")):
            os.environ["U2NET_HOME"] = path
            break
