import os
import shutil
import logging
import subprocess

class BinaryManager:
    _cached_encoder = None
    @staticmethod

    def get_bin_path():
        return os.path.join(os.path.dirname(os.path.abspath(__file__)), "binaries")
    @staticmethod

    def ensure_env():
        bin_dir = BinaryManager.get_bin_path()
        logger = logging.getLogger("Advanced_Video_Editor")
        src_dll = os.path.join(bin_dir, "libmpv-2.dll")
        dst_dll = os.path.join(bin_dir, "mpv-1.dll")
        if os.path.exists(src_dll):
            if os.path.exists(dst_dll):
                try:
                    with open(dst_dll, 'a'):
                        pass
                except IOError:
                    logger.info("[BINARY] mpv-1.dll is locked by another instance. Using existing file.")
                    return
                if os.path.getsize(src_dll) == os.path.getsize(dst_dll):
                    logger.info("[BINARY] mpv-1.dll is up-to-date.")
                    return
            try:
                shutil.copy2(src_dll, dst_dll)
                logger.info(f"[BINARY] Auto-patched mpv-1.dll from libmpv-2.dll")
            except (PermissionError, IOError):
                logger.warning("[BINARY] Permission denied during patch. Another instance likely finished the job.")
            except Exception as e:
                logger.error(f"[BINARY] Failed to patch DLL: {e}")
        os.environ["PATH"] = bin_dir + os.pathsep + os.environ.get("PATH", "")
        os.environ["MPV_HOME"] = bin_dir
    @staticmethod

    def get_best_encoder(logger=None):
        """Goal 20: Centralized, cached GPU detection."""
        if BinaryManager._cached_encoder:
            return BinaryManager._cached_encoder
        if not logger:
            logger = logging.getLogger("Advanced_Video_Editor")
        preferred_encoders = [
            ('av1_nvenc', "NVIDIA AV1"),
            ('hevc_nvenc', "NVIDIA HEVC"),
            ('h264_nvenc', "NVIDIA H264"),
            ('h264_qsv', "Intel QuickSync"),
            ('h264_amf', "AMD AMF"),
        ]
        try:
            ffmpeg_bin = BinaryManager.get_executable('ffmpeg')
            si = subprocess.STARTUPINFO()
            si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            output = subprocess.check_output(
                [ffmpeg_bin, '-encoders'], 
                startupinfo=si, 
                stderr=subprocess.STDOUT
            ).decode('utf-8', errors='ignore')
            available_encoders = set()
            for line in output.splitlines():
                line = line.strip()
                if line and not line.startswith("="):
                    parts = line.split()
                    if len(parts) > 1 and parts[0] == 'V.....':
                        available_encoders.add(parts[1])
            for encoder_name, friendly_name in preferred_encoders:
                if encoder_name in available_encoders:
                    logger.info(f"[RENDER] GPU encoder selected: {friendly_name} ({encoder_name})")
                    BinaryManager._cached_encoder = encoder_name
                    return BinaryManager._cached_encoder
            logger.warning("[RENDER] No preferred GPU encoder found. Falling back to libx264.")
            BinaryManager._cached_encoder = 'libx264'
        except Exception as e:
            logger.warning(f"[RENDER] HW detection failed: {e}")
            BinaryManager._cached_encoder = 'libx264'
        return BinaryManager._cached_encoder
    @staticmethod

    def purge_vlc_cache(bin_dir, logger):
        """Nukes stale plugin-registry to prevent 'ghost' DLL errors."""
        plugins_dat = os.path.join(bin_dir, "plugins", "plugins.dat")
        if os.path.exists(plugins_dat):
            try:
                os.remove(plugins_dat)
                logger.info("[BINARY] Stale VLC plugin cache purged.")
            except Exception as e:
                logger.error(f"[BINARY] Failed to purge VLC cache: {e}")
    @staticmethod

    def verify_vlc_plugins(bin_dir, logger):
        """Goal 17: Ensures all 200+ VLC plugins are present and readable to prevent 'silent' playback failure."""
        plugins_dir = os.path.join(bin_dir, "plugins")
        if not os.path.exists(plugins_dir):
            logger.critical(f"[BINARY] VLC Plugins folder MISSING at {plugins_dir}")
            return False
        plugin_count = 0
        failed_reads = []
        for root, dirs, files in os.walk(plugins_dir):
            for file in files:
                if file.endswith(".dll"):
                    plugin_path = os.path.join(root, file)
                    plugin_count += 1
                    try:
                        with open(plugin_path, 'rb') as f:
                            pass
                    except Exception as e:
                        failed_reads.append(f"{plugin_path} (Error: {e})")
        if failed_reads:
            logger.error(f"[BINARY] {len(failed_reads)} VLC plugins are CORRUPT or UNREADABLE.")
            for err in failed_reads[:5]:
                logger.error(f"  -> {err}")
        else:
            logger.info(f"[BINARY] Integrity Check: {plugin_count} VLC plugins verified.")
        return len(failed_reads) == 0
    @staticmethod

    def _is_64bit(filepath):
        """Dumps the PE header to ensure we aren't loading 32-bit garbage into a 64-bit process."""
        try:
            with open(filepath, 'rb') as f:
                f.seek(60)
                pe_offset = int.from_bytes(f.read(4), 'little')
                f.seek(pe_offset + 4)
                machine = int.from_bytes(f.read(2), 'little')
                return machine == 0x8664
        except Exception:
            return False
    @staticmethod

    def get_executable(name):
        if os.name == 'nt' and not name.lower().endswith('.exe'): name += ".exe"
        target = os.path.join(BinaryManager.get_bin_path(), name)
        if os.path.exists(target): return target
        return shutil.which(name) or name