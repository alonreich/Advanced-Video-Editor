import os
import shutil
import logging

class BinaryManager:
    @staticmethod
    def get_bin_path():
        return os.path.join(os.path.dirname(os.path.abspath(__file__)), "binaries")
    @staticmethod
    def ensure_env():
        bin_dir = BinaryManager.get_bin_path()
        logger = logging.getLogger("Advanced_Video_Editor")
        src_dll = os.path.join(bin_dir, "libmpv-2.dll")
        dst_dll = os.path.join(bin_dir, "mpv-1.dll")
        if os.path.exists(src_dll) and not os.path.exists(dst_dll):
            try:
                shutil.copy2(src_dll, dst_dll)
                logger.info(f"[BINARY] Auto-patched mpv-1.dll from libmpv-2.dll")
            except Exception as e:
                logger.error(f"[BINARY] Failed to patch DLL: {e}")
        os.environ["PATH"] = bin_dir + os.pathsep + os.environ.get("PATH", "")
        os.environ["MPV_HOME"] = bin_dir
    @staticmethod
    def get_executable(name):
        if os.name == 'nt' and not name.lower().endswith('.exe'): name += ".exe"
        target = os.path.join(BinaryManager.get_bin_path(), name)
        if os.path.exists(target): return target
        return shutil.which(name) or name
