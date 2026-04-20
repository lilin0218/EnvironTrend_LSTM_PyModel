import os
import sys
import time
import threading
from enum import Enum


class LogLevel(Enum):
    DEBUG = 0
    INFO = 1
    WARNING = 2
    ERROR = 3
    CRITICAL = 4


class Logger:
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super(Logger, cls).__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        
        self._log_level = LogLevel.DEBUG
        self._log_file = None
        self._mutex = threading.Lock()
        
        exe_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
        log_dir = os.path.join(exe_dir, 'log')
        os.makedirs(log_dir, exist_ok=True)
        
        timestamp = time.strftime("%Y%m%d")
        log_filename = f"app_{timestamp}.log"
        self._log_path = os.path.join(log_dir, log_filename)
        
        self._initialized = True

    @staticmethod
    def instance():
        return Logger()

    def _level_to_string(self, level):
        return {
            LogLevel.DEBUG: "DEBUG",
            LogLevel.INFO: "INFO",
            LogLevel.WARNING: "WARNING",
            LogLevel.ERROR: "ERROR",
            LogLevel.CRITICAL: "CRITICAL"
        }.get(level, "UNKNOWN")

    def _write_log(self, level, module, message):
        if level.value < self._log_level.value:
            return

        with self._mutex:
            timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
            level_str = self._level_to_string(level)
            log_line = f"[{timestamp}] [{level_str}] [{module}] {message}\n"
            
            try:
                with open(self._log_path, 'a', encoding='utf-8') as f:
                    f.write(log_line)
            except Exception as e:
                print(f"Failed to write log: {e}")

    def debug(self, module, message):
        self._write_log(LogLevel.DEBUG, module, message)

    def info(self, module, message):
        self._write_log(LogLevel.INFO, module, message)

    def warning(self, module, message):
        self._write_log(LogLevel.WARNING, module, message)

    def error(self, module, message):
        self._write_log(LogLevel.ERROR, module, message)

    def critical(self, module, message):
        self._write_log(LogLevel.CRITICAL, module, message)

    def set_log_level(self, level):
        if isinstance(level, LogLevel):
            self._log_level = level
