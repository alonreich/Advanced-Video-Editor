import sys
import os
import logging
import json
import threading
from logging.handlers import RotatingFileHandler

class StreamToLogger:
    """Redirects stdout/stderr to the logger."""

    def __init__(self, logger, level):
        self.logger = logger
        self.level = level

    def write(self, buf):
        for line in buf.rstrip().splitlines():
            self.logger.log(self.level, line.rstrip())

    def flush(self): pass

def setup_system(base_dir):
    log_dir = os.path.abspath(os.path.join(base_dir, '..', 'logs'))
    os.makedirs(log_dir, exist_ok=True)
    log_dir2 = os.path.abspath(os.path.join(base_dir, 'logs'))
    os.makedirs(log_dir2, exist_ok=True)
    fmt = logging.Formatter('%(asctime)s | %(name)-10s | %(levelname)-8s | %(message)s')
    logger = logging.getLogger("Advanced_Video_Editor")
    logger.setLevel(logging.DEBUG)
    for d in [log_dir, log_dir2]:
        f_path = os.path.join(d, 'Advanced_Video_Editor.log')
        h = RotatingFileHandler(f_path, maxBytes=10*1024*1024, backupCount=5, encoding='utf-8')
        h.setFormatter(fmt)
        logger.addHandler(h)
    return logger

class ConfigManager:

    def __init__(self, path):
        self.path = path
        self.data = {}
        self.lock = threading.Lock()
        self.load()

    def load(self):
        with self.lock:
            if os.path.exists(self.path):
                try:
                    with open(self.path, 'r') as f: self.data = json.load(f)
                except: self.data = {}

    def save(self):
        with self.lock:
            os.makedirs(os.path.dirname(self.path), exist_ok=True)
            with open(self.path, 'w') as f: json.dump(self.data, f, indent=4)

    def get(self, k, default=None): return self.data.get(k, default)

    def set(self, k, v):
        self.data[k] = v
        self.save()
