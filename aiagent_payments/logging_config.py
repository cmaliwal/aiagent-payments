"""
Logging configuration for the AI Agent Payments SDK.

This module provides centralized logging configuration and utilities
for consistent logging across all SDK components.

# TODO: Dynamic log level changes, handler removal by name/type, and performance threshold alerts are planned for future releases. See function-level TODOs for details.
"""

import logging
import logging.handlers
import os
import re
import sys
import tempfile
from pathlib import Path
from typing import Any

# Cross-platform file locking
try:
    import fcntl

    _has_fcntl = True
except ImportError:
    _has_fcntl = False

# Windows-specific file locking
try:
    import msvcrt

    _has_msvcrt = True
except ImportError:
    _has_msvcrt = False


class SecretRedactor(logging.Filter):
    SECRET_PATTERNS = [
        # Stripe patterns
        re.compile(r"(sk_live_[a-zA-Z0-9]+)", re.IGNORECASE),
        re.compile(r"(sk_test_[a-zA-Z0-9]+)", re.IGNORECASE),
        re.compile(r"(whsec_[a-zA-Z0-9]+)", re.IGNORECASE),
        re.compile(r"(pi_[a-zA-Z0-9]+)", re.IGNORECASE),
        re.compile(r"(ch_[a-zA-Z0-9]+)", re.IGNORECASE),
        # PayPal patterns
        re.compile(r"(client-id:[a-zA-Z0-9\-]+)", re.IGNORECASE),
        re.compile(r"(client_secret:[a-zA-Z0-9\-]+)", re.IGNORECASE),
        re.compile(r"(access_token=)[^&\s]+", re.IGNORECASE),
        # CryptoProvider patterns
        re.compile(r"(0x[a-fA-F0-9]{40})"),  # Ethereum wallet address
        re.compile(r"(0x[a-fA-F0-9]{64})"),  # Ethereum transaction hash
        re.compile(r"(0x[a-fA-F0-9]{66})"),  # Ethereum private key (with 0x prefix)
        re.compile(r"\b[a-fA-F0-9]{64}\b"),  # Non-prefixed private key
        re.compile(r"(usdc|usdt|dai|busd|gusd)[:=][a-zA-Z0-9]+", re.IGNORECASE),
        # Generic patterns
        re.compile(r"(key=)[a-zA-Z0-9\-_\.]+", re.IGNORECASE),
        re.compile(r"(client_secret=)[^&\s]+", re.IGNORECASE),
        re.compile(r"(api_key=)[^&\s]+", re.IGNORECASE),
        re.compile(r"(password=)[^&\s]+", re.IGNORECASE),
        re.compile(r"(secret=)[^&\s]+", re.IGNORECASE),
        re.compile(r"(token=)[^&\s]+", re.IGNORECASE),
        re.compile(r"(Bearer )[a-zA-Z0-9\-_\.]+", re.IGNORECASE),
        re.compile(r"(Authorization: )[a-zA-Z0-9\-_\.]+", re.IGNORECASE),
    ]

    def filter(self, record):
        """Redact sensitive data from log messages and arguments."""
        formatted_msg = str(record.msg)
        for pattern in self.SECRET_PATTERNS:
            formatted_msg = pattern.sub(lambda m: m.group(1) + "***REDACTED***", formatted_msg)

        redacted_args = []
        if record.args:
            for arg in record.args:
                arg_str = str(arg)
                for pattern in self.SECRET_PATTERNS:
                    arg_str = pattern.sub(lambda m: m.group(1) + "***REDACTED***", arg_str)
                redacted_args.append(arg_str)

        record.msg = formatted_msg
        record.args = tuple(redacted_args) if redacted_args else ()
        return True


def _get_lock_file_path():
    """Get the lock file path with fallback to writable directories."""
    process_id = os.getpid()
    lock_filename = f"aiagent_payments_logging_{process_id}.lock"

    def _validate_path_length(path):
        """Validate if the resolved path length is within system limits."""
        try:
            resolved_path = os.path.abspath(path)
            max_length = 260 if os.name == "nt" else 4096
            if len(resolved_path) > max_length:
                return False
            return True
        except Exception:
            return False

    config_path = os.environ.get("AIAgentPayments_LockFile")
    if config_path:
        try:
            if not _validate_path_length(config_path):
                logging.debug("User-configured lock file path exceeds system length limits: %s", config_path)
                raise ValueError("Path too long")

            lock_dir = os.path.dirname(config_path)
            if not os.path.exists(lock_dir):
                os.makedirs(lock_dir, exist_ok=True)
            if os.access(lock_dir, os.W_OK):
                test_file = os.path.join(lock_dir, ".test_write")
                try:
                    with open(test_file, "w") as f:
                        f.write("test")
                    os.remove(test_file)
                    return config_path
                except (OSError, IOError):
                    pass
        except Exception:
            pass

    fallback_dirs = [
        tempfile.gettempdir(),
        "/tmp",
        "/var/tmp",
        os.path.expanduser("~/.cache"),
        os.path.expanduser("~/.tmp"),
    ]

    for temp_dir in fallback_dirs:
        try:
            if os.path.exists(temp_dir) and os.access(temp_dir, os.W_OK):
                potential_lock_path = os.path.join(temp_dir, lock_filename)
                if not _validate_path_length(potential_lock_path):
                    logging.debug("Lock file path would exceed system length limits in %s", temp_dir)
                    continue

                test_file = os.path.join(temp_dir, ".test_write")
                try:
                    with open(test_file, "w") as f:
                        f.write("test")
                    os.remove(test_file)
                    return potential_lock_path
                except (OSError, IOError):
                    continue
        except Exception:
            continue

    try:
        if os.access(".", os.W_OK):
            potential_lock_path = os.path.abspath(lock_filename)
            if not _validate_path_length(potential_lock_path):
                logging.debug("Lock file path would exceed system length limits in current directory")
                raise ValueError("Path too long")

            test_file = ".test_write"
            try:
                with open(test_file, "w") as f:
                    f.write("test")
                os.remove(test_file)
                return lock_filename
            except (OSError, IOError):
                pass
    except Exception:
        pass

    raise ValueError(
        f"No writable directory found for lock file. Tried: user config path, {', '.join(fallback_dirs)}, and current directory. "
        "Please set AIAgentPayments_LockFile environment variable to a writable path."
    )


class ColoredFormatter(logging.Formatter):
    """Custom formatter that adds colors to log messages."""

    COLORS = {
        "DEBUG": "\033[36m",  # Cyan
        "INFO": "\033[32m",  # Green
        "WARNING": "\033[33m",  # Yellow
        "ERROR": "\033[31m",  # Red
        "CRITICAL": "\033[35m",  # Magenta
        "RESET": "\033[0m",  # Reset
    }

    def format(self, record):
        """Format the log record with colors."""
        if record.levelname in self.COLORS:
            record.levelname = f"{self.COLORS[record.levelname]}{record.levelname}{self.COLORS['RESET']}"
        return super().format(record)


def _acquire_dir_lock():
    """Acquire file-based lock for directory creation."""
    _cleanup_stale_lock_file()

    lock_file = None
    lock_acquired = False

    try:
        lock_file_path = _get_lock_file_path()

        if _has_fcntl:
            lock_file = open(lock_file_path, "w+b")
            try:
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
                lock_acquired = True
            except Exception as e:
                try:
                    lock_file.close()
                    if os.path.exists(lock_file_path):
                        os.remove(lock_file_path)
                        logging.debug("Cleaned up lock file after Unix lock failure: %s", lock_file_path)
                except Exception as cleanup_error:
                    logging.debug("Failed to clean up lock file after Unix lock failure: %s", cleanup_error)
                raise e
        elif _has_msvcrt:
            import time

            max_attempts = 10
            retry_delay = 0.1
            timeout_start = time.time()
            max_timeout = 3.0

            for attempt in range(max_attempts):
                lock_file = None
                try:
                    lock_file = open(lock_file_path, "w+b")
                    msvcrt.locking(lock_file.fileno(), msvcrt.LK_NBLCK, 1)
                    lock_acquired = True
                    break
                except (OSError, IOError) as e:
                    if lock_file:
                        try:
                            lock_file.close()
                            if os.path.exists(lock_file_path):
                                os.remove(lock_file_path)
                                logging.debug("Cleaned up lock file after Windows lock attempt %d failure", attempt + 1)
                        except Exception as cleanup_error:
                            logging.debug("Failed to clean up lock file after Windows lock attempt: %s", cleanup_error)
                    if time.time() - timeout_start > max_timeout:
                        logging.warning("Windows lock acquisition timeout after %d attempts: %s", attempt + 1, e)
                        return None
                    time.sleep(retry_delay)
                    retry_delay = min(retry_delay * 1.5, 0.5)
                    if attempt == max_attempts - 1:
                        logging.warning(
                            "Failed to acquire Windows lock after %d attempts, falling back to console-only logging", max_attempts
                        )
                        return None
        else:
            import time

            max_attempts = 50
            timeout_start = time.time()
            max_timeout = 5.0

            for attempt in range(max_attempts):
                lock_file = None
                try:
                    lock_file = open(lock_file_path, "x")
                    lock_acquired = True
                    break
                except FileExistsError:
                    if lock_file:
                        try:
                            lock_file.close()
                        except Exception:
                            pass
                    if time.time() - timeout_start > max_timeout:
                        raise TimeoutError(f"Failed to acquire directory lock after {max_timeout} seconds")
                    if attempt == max_attempts - 1:
                        raise TimeoutError(f"Failed to acquire directory lock after {max_attempts} attempts")
                    time.sleep(0.1)
                finally:
                    if lock_file and not lock_acquired:
                        try:
                            lock_file.close()
                        except Exception:
                            pass

        return lock_file
    except ValueError as e:
        logging.error("Lock file path validation failed: %s", e)
        logging.warning("Falling back to console-only logging due to lock file path issues")
        return None
    except Exception as e:
        logging.error("Failed to acquire directory lock: %s", e)
        if lock_file and not lock_acquired:
            try:
                lock_file.close()
                if os.path.exists(lock_file_path):
                    os.remove(lock_file_path)
                    logging.debug("Cleaned up orphaned lock file after acquisition failure")
                lock_file = None
            except Exception as cleanup_error:
                logging.warning("Failed to clean up orphaned lock file: %s", cleanup_error)
        elif lock_file:
            lock_file.close()
            lock_file = None
        raise


def _cleanup_stale_lock_file():
    """Clean up stale lock files from crashed processes."""
    try:
        try:
            lock_file_path = _get_lock_file_path()
        except ValueError:
            return

        lock_dir = os.path.dirname(lock_file_path)
        lock_pattern = "aiagent_payments_logging_*.lock"
        cleaned_count = 0
        import glob
        import time

        try:
            lock_files = glob.glob(os.path.join(lock_dir, lock_pattern))
            for lock_file in lock_files:
                try:
                    file_age = time.time() - os.path.getmtime(lock_file)
                    if file_age > 30:
                        try:
                            os.remove(lock_file)
                            cleaned_count += 1
                        except OSError as e:
                            logging.debug("Failed to clean up stale lock file %s: %s", lock_file, e)
                except OSError as e:
                    logging.debug("Error accessing lock file %s: %s", lock_file, e)
            if cleaned_count > 0:
                logging.debug(f"Cleaned up {cleaned_count} stale lock files in {lock_dir}")
        except Exception as e:
            logging.debug("Error scanning for stale lock files in %s: %s", lock_dir, e)
    except Exception as e:
        logging.debug("Error in stale lock file cleanup: %s", e)


def _release_dir_lock(lock_file):
    """Release file-based lock."""
    try:
        if _has_fcntl:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
        elif _has_msvcrt:
            msvcrt.locking(lock_file.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            try:
                lock_file_path = _get_lock_file_path()
                os.remove(lock_file_path)
            except ValueError as e:
                logging.debug("Lock file path validation failed during release: %s", e)
            except OSError as e:
                logging.debug("Failed to remove lock file during release (OSError): %s", e)
    except Exception as e:
        logging.error("Failed to release directory lock: %s", e)
        if not _has_fcntl and not _has_msvcrt:
            try:
                lock_file_path = _get_lock_file_path()
                os.remove(lock_file_path)
            except ValueError as cleanup_path_error:
                logging.debug("Lock file path validation failed during cleanup: %s", cleanup_path_error)
            except Exception as cleanup_error:
                logging.debug("Failed to remove lock file after lock release failure: %s", cleanup_error)
    finally:
        try:
            lock_file.close()
        except Exception:
            pass


def _validate_log_file_path(log_file: str) -> bool:
    """Validate log file path for writability and valid characters."""
    try:
        log_path = Path(log_file)
        invalid_chars = '<>:"|?*'
        if any(char in str(log_path) for char in invalid_chars):
            return False
        abs_path = log_path.resolve()
        if len(str(abs_path)) > 260:
            return False
        parent = log_path.parent
        if parent.exists() and not os.access(parent, os.W_OK):
            return False
        return True
    except Exception:
        return False


def _ensure_secret_redactor_on_handlers() -> None:
    """Ensure SecretRedactor filter is applied to all existing handlers."""
    root_logger = logging.getLogger()
    secret_redactor = SecretRedactor()

    for handler in root_logger.handlers:
        has_secret_redactor = any(isinstance(f, SecretRedactor) for f in handler.filters)
        if not has_secret_redactor:
            handler.addFilter(secret_redactor)


def setup_logging(
    level: str = "INFO",
    log_file: str | None = None,
    log_format: str | None = None,
    max_bytes: int = 10 * 1024 * 1024,
    backup_count: int = 5,
    use_colors: bool = True,
    include_timestamp: bool = True,
    clear_handlers: bool = False,
) -> None:
    """Set up logging configuration for the AI Agent Payments SDK."""
    if not isinstance(max_bytes, int) or max_bytes <= 0:
        max_bytes = 10 * 1024 * 1024
    if not isinstance(backup_count, int) or backup_count < 0:
        backup_count = 5

    valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
    level = level.upper()
    if level not in valid_levels:
        logging.warning("Invalid log level %s, defaulting to INFO", level)
        level = "INFO"

    log_level = getattr(logging, level)

    if log_format is None:
        if include_timestamp:
            log_format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        else:
            log_format = "%(name)s - %(levelname)s - %(message)s"

    try:
        _ = logging.Formatter(log_format)
    except Exception as e:
        logging.warning("Invalid log format '%s': %s. Using default format.", log_format, e)
        if include_timestamp:
            log_format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        else:
            log_format = "%(name)s - %(levelname)s - %(message)s"

    env_use_colors = os.environ.get("AIAgentPayments_LogColors", "true").lower() == "true"
    use_colors = use_colors and env_use_colors and sys.stderr.isatty()

    if use_colors:
        console_formatter = ColoredFormatter(log_format)
    else:
        console_formatter = logging.Formatter(log_format)

    file_formatter = logging.Formatter(log_format)

    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)

    if clear_handlers:
        if root_logger.handlers:
            logging.warning("Clearing existing handlers as requested. This may affect other logging configurations.")
        for handler in root_logger.handlers[:]:
            root_logger.removeHandler(handler)

    console_handler = logging.StreamHandler(sys.stderr)
    console_handler.setLevel(log_level)
    console_handler.setFormatter(console_formatter)
    console_handler.addFilter(SecretRedactor())
    root_logger.addHandler(console_handler)

    if log_file:
        if not _validate_log_file_path(log_file):
            logging.error("Invalid log file path: %s", log_file)
            raise ValueError(f"Invalid log file path: {log_file}")

        lock_file = None
        try:
            log_path = Path(log_file)
            lock_file = _acquire_dir_lock()
            if lock_file is None:
                logging.warning("Skipping file handler setup due to lock file issues. Falling back to console-only logging.")
                _ensure_secret_redactor_on_handlers()
                return

            try:
                if lock_file is not None:
                    log_path.parent.mkdir(parents=True, exist_ok=True)
                else:
                    log_path.parent.mkdir(parents=True, exist_ok=True)
            finally:
                if lock_file is not None:
                    try:
                        _release_dir_lock(lock_file)
                    except Exception as lock_error:
                        logging.debug("Failed to release directory lock during cleanup: %s", lock_error)

            try:
                file_handler = logging.handlers.RotatingFileHandler(
                    log_file, maxBytes=max_bytes, backupCount=backup_count, encoding="utf-8"
                )
                file_handler.setLevel(log_level)
                file_handler.setFormatter(file_formatter)
                file_handler.addFilter(SecretRedactor())
                root_logger.addHandler(file_handler)
            except (OSError, IOError, ValueError) as e:
                logging.error("Failed to create rotating file handler for %s: %s", log_file, e)
                _ensure_secret_redactor_on_handlers()
                raise
        except PermissionError as e:
            logging.error("Permission denied for log file %s: %s", log_file, e)
            if lock_file is not None:
                try:
                    _release_dir_lock(lock_file)
                except Exception as lock_error:
                    logging.debug("Failed to release directory lock during cleanup: %s", lock_error)
            _ensure_secret_redactor_on_handlers()
            raise
        except OSError as e:
            logging.error("OS error for log file %s: %s", log_file, e)
            if lock_file is not None:
                try:
                    _release_dir_lock(lock_file)
                except Exception as lock_error:
                    logging.debug("Failed to release directory lock during cleanup: %s", lock_error)
            _ensure_secret_redactor_on_handlers()
            raise
        except Exception as e:
            logging.error("Failed to configure file handler for %s: %s", log_file, e)
            if lock_file is not None:
                try:
                    _release_dir_lock(lock_file)
                except Exception as lock_error:
                    logging.debug("Failed to release directory lock during cleanup: %s", lock_error)
            _ensure_secret_redactor_on_handlers()
            raise

    sdk_loggers = [
        "aiagent_payments",
        "aiagent_payments.core",
        "aiagent_payments.storage",
        "aiagent_payments.providers",
        "aiagent_payments.models",
        "aiagent_payments.exceptions",
        "aiagent_payments.crypto",
    ]

    for logger_name in sdk_loggers:
        logger = logging.getLogger(logger_name)
        logger.setLevel(log_level)
        logger.propagate = False

    logging.info(f"Logging configured - Level: {level}, File: {log_file or 'None'}, Colors: {use_colors}")


def get_logger(name: str) -> logging.Logger:
    """Get a logger instance for the specified name."""
    if not name or not isinstance(name, str) or not name.strip():
        logging.warning("Invalid logger name provided: %s", repr(name))
        raise ValueError("Logger name must be a non-empty string")

    logger = logging.getLogger(name)
    if name.startswith("aiagent_payments"):
        logger.propagate = False
    return logger


def set_log_level(level: str, logger_name: str | None = None) -> None:
    """Set the log level for a specific logger or all loggers."""
    valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
    level = level.upper()
    if level not in valid_levels:
        logging.warning("Invalid log level %s, defaulting to INFO", level)
        level = "INFO"

    log_level = getattr(logging, level)

    if logger_name:
        logger = logging.getLogger(logger_name)
        if logger_name.startswith("aiagent_payments") and logger.propagate:
            logging.warning(
                "SDK logger '%s' has propagate=True which may cause sensitive data leakage. "
                "Setting propagate=False for security compliance.",
                logger_name,
            )
            logger.propagate = False
        logger.setLevel(log_level)
        logging.info(f"Set log level for {logger_name} to {level}")
    else:
        logging.getLogger().setLevel(log_level)
        logging.info(f"Set root log level to {level}")


def add_file_handler(
    log_file: str,
    level: str = "INFO",
    max_bytes: int = 10 * 1024 * 1024,
    backup_count: int = 5,
    formatter: logging.Formatter | None = None,
) -> None:
    """Add a file handler to the root logger."""
    if not isinstance(max_bytes, int) or max_bytes <= 0:
        max_bytes = 10 * 1024 * 1024
    if not isinstance(backup_count, int) or backup_count < 0:
        backup_count = 5

    log_level = getattr(logging, level.upper(), logging.INFO)

    if not _validate_log_file_path(log_file):
        logging.error("Invalid log file path: %s", log_file)
        raise ValueError(f"Invalid log file path: {log_file}")

    log_path = Path(log_file)
    lock_file = None
    try:
        lock_file = _acquire_dir_lock()
        if lock_file is None:
            logging.warning("Skipping file handler setup due to lock file issues. Falling back to console-only logging.")
            _ensure_secret_redactor_on_handlers()
            raise ValueError("Failed to acquire directory lock for log file. Falling back to console-only logging.")

        try:
            if lock_file is not None:
                log_path.parent.mkdir(parents=True, exist_ok=True)
            else:
                log_path.parent.mkdir(parents=True, exist_ok=True)
        finally:
            if lock_file is not None:
                try:
                    _release_dir_lock(lock_file)
                except Exception as lock_error:
                    logging.debug("Failed to release directory lock during cleanup: %s", lock_error)

        try:
            file_handler = logging.handlers.RotatingFileHandler(
                log_file, maxBytes=max_bytes, backupCount=backup_count, encoding="utf-8"
            )
            file_handler.setLevel(log_level)
            if formatter:
                file_handler.setFormatter(formatter)
            else:
                file_handler.setFormatter(logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s"))
            file_handler.addFilter(SecretRedactor())
            logging.getLogger().addHandler(file_handler)
            logging.info(f"Added file handler: {log_file} (level: {level})")
        except (OSError, IOError, ValueError) as e:
            logging.error("Failed to create rotating file handler for %s: %s", log_file, e)
            _ensure_secret_redactor_on_handlers()
            raise
    except PermissionError as e:
        logging.error("Permission denied for log file %s: %s", log_file, e)
        if lock_file is not None:
            try:
                _release_dir_lock(lock_file)
            except Exception as lock_error:
                logging.debug("Failed to release directory lock during cleanup: %s", lock_error)
        _ensure_secret_redactor_on_handlers()
        raise
    except OSError as e:
        logging.error("OS error for log file %s: %s", log_file, e)
        if lock_file is not None:
            try:
                _release_dir_lock(lock_file)
            except Exception as lock_error:
                logging.debug("Failed to release directory lock during cleanup: %s", lock_error)
        _ensure_secret_redactor_on_handlers()
        raise
    except Exception as e:
        logging.error("Failed to add file handler for %s: %s", log_file, e)
        if lock_file is not None:
            try:
                _release_dir_lock(lock_file)
            except Exception as lock_error:
                logging.debug("Failed to release directory lock during cleanup: %s", lock_error)
        _ensure_secret_redactor_on_handlers()
        raise


def remove_file_handler(log_file: str) -> bool:
    """Remove a file handler from the root logger."""
    root_logger = logging.getLogger()
    for handler in root_logger.handlers[:]:
        if isinstance(handler, logging.handlers.RotatingFileHandler) and handler.baseFilename == os.path.abspath(log_file):
            root_logger.removeHandler(handler)
            logging.info("Removed file handler: %s", log_file)
            _ensure_secret_redactor_on_handlers()
            return True
    logging.warning("File handler not found: %s", log_file)
    return False


def log_function_call(func_name: str, args: tuple, kwargs: dict, logger: logging.Logger | None = None) -> None:
    """Log a function call with its arguments."""
    if logger is None:
        logger = logging.getLogger()

    args_str = ", ".join(repr(arg) for arg in args)
    kwargs_str = ", ".join(f"{k}={repr(v)}" for k, v in kwargs.items())

    secret_redactor = SecretRedactor()
    for pattern in secret_redactor.SECRET_PATTERNS:
        args_str = pattern.sub(lambda m: m.group(1) + "***REDACTED***", args_str)
        kwargs_str = pattern.sub(lambda m: m.group(1) + "***REDACTED***", kwargs_str)

    if args_str and kwargs_str:
        call_str = f"{func_name}({args_str}, {kwargs_str})"
    elif args_str:
        call_str = f"{func_name}({args_str})"
    elif kwargs_str:
        call_str = f"{func_name}({kwargs_str})"
    else:
        call_str = f"{func_name}()"

    logger.debug("Function call: %s", call_str)


def log_performance(
    func_name: str,
    start_time: float,
    end_time: float,
    logger: logging.Logger | None = None,
    level: str = "DEBUG",
    precision: int = 6,
) -> None:
    """Log performance metrics for a function."""
    valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
    if level.upper() not in valid_levels:
        level = "DEBUG"

    if not isinstance(precision, int) or precision < 0 or precision > 10:
        precision = 6

    if logger is None:
        logger = logging.getLogger()

    if end_time <= start_time:
        logger.warning(
            "Invalid performance timing for %s: end_time (%.6f) <= start_time (%.6f). Skipping performance log.",
            func_name,
            end_time,
            start_time,
        )
        return

    duration = end_time - start_time
    logger.log(getattr(logging, level.upper(), logging.DEBUG), f"Performance: {func_name} took {duration:.{precision}f} seconds")


def create_structured_logger(name: str, extra_fields: dict[str, Any] | None = None) -> logging.Logger:
    """Create a logger that automatically includes extra fields in log messages."""
    logger = logging.getLogger(name)
    if name.startswith("aiagent_payments"):
        logger.propagate = False

    if logger.handlers:
        secret_redactor = SecretRedactor()
        for handler in logger.handlers:
            has_secret_redactor = any(isinstance(f, SecretRedactor) for f in handler.filters)
            if not has_secret_redactor:
                handler.addFilter(secret_redactor)

    if extra_fields:
        sanitized_fields = {}
        total_length = 0
        field_count = 0
        max_fields = 5
        max_total_length = 1000

        for key, value in extra_fields.items():
            if field_count >= max_fields or total_length >= max_total_length:
                break
            if isinstance(value, str) and any(pattern.search(value) for pattern in SecretRedactor.SECRET_PATTERNS):
                sanitized_fields[key] = "***REDACTED***"
            else:
                sanitized_fields[key] = str(value)[:100] if len(str(value)) > 100 else str(value)
            total_length += len(str(sanitized_fields[key]))
            field_count += 1

        if len(extra_fields) > max_fields or total_length >= max_total_length:
            sanitized_fields["_truncated"] = f"... ({len(extra_fields) - field_count} more fields)"

        logger.debug(f"Creating structured logger: {name} with {len(extra_fields)} extra fields")
        logger.debug(f"Sanitized extra fields (limited): {sanitized_fields}")

        class SecureExtraFieldsAdapter(logging.LoggerAdapter):
            def __init__(self, logger, extra_fields):
                super().__init__(logger, extra_fields)
                self._secret_redactor = SecretRedactor()
                self._logger_name = name
                self._ensure_secret_redactor_on_handlers()
                self._original_add_handler = logger.addHandler
                logger.addHandler = self._secure_add_handler

            def _ensure_secret_redactor_on_handlers(self):
                for handler in self.logger.handlers:
                    has_secret_redactor = any(isinstance(f, SecretRedactor) for f in handler.filters)
                    if not has_secret_redactor:
                        handler.addFilter(self._secret_redactor)
                        logging.debug("Applied SecretRedactor to handler in structured logger: %s", self._logger_name)

            def _secure_add_handler(self, handler):
                has_secret_redactor = any(isinstance(f, SecretRedactor) for f in handler.filters)
                if not has_secret_redactor:
                    handler.addFilter(self._secret_redactor)
                    logging.debug("Applied SecretRedactor to new handler in structured logger: %s", self._logger_name)
                return self._original_add_handler(handler)

            def process(self, msg, kwargs):
                extra = kwargs.get("extra", {})
                if self.extra:
                    extra.update(self.extra)
                kwargs["extra"] = extra
                return msg, kwargs

        return SecureExtraFieldsAdapter(logger, extra_fields)  # type: ignore
    else:
        logger.debug(f"Creating basic structured logger: {name}")

    return logger


def setup_default_logging() -> None:
    """Set up default logging configuration for the SDK."""
    if logging.getLogger().handlers:
        _ensure_secret_redactor_on_handlers()
        return

    try:
        setup_logging(
            level=os.environ.get("AIAgentPayments_LogLevel", "INFO"),
            log_file=os.environ.get("AIAgentPayments_LogFile"),
            use_colors=os.environ.get("AIAgentPayments_LogColors", "true").lower() == "true",
            clear_handlers=False,
        )
    except Exception as e:
        try:
            root_logger = logging.getLogger()
            root_logger.handlers = []
            setup_logging(
                level="INFO",
                log_file=None,
                use_colors=False,
                clear_handlers=True,
            )
            logging.error("Failed to configure logging: %s. Using minimal console logging.", e)
        except Exception as fallback_error:
            try:
                root_logger = logging.getLogger()
                root_logger.handlers = []
                root_logger.setLevel(logging.INFO)
                console_handler = logging.StreamHandler(sys.stderr)
                console_handler.setLevel(logging.INFO)
                console_handler.setFormatter(logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s"))
                console_handler.addFilter(SecretRedactor())
                root_logger.addHandler(console_handler)
                logging.error("Failed to configure logging: %s. Using manual console logging with redaction.", fallback_error)
            except Exception as final_error:
                try:
                    root_logger = logging.getLogger()
                    root_logger.handlers = []
                    root_logger.setLevel(logging.INFO)
                    root_logger.propagate = False
                    console_handler = logging.StreamHandler(sys.stderr)
                    console_handler.setLevel(logging.INFO)
                    console_handler.setFormatter(logging.Formatter("%(levelname)s - %(message)s"))
                    console_handler.addFilter(SecretRedactor())
                    root_logger.addHandler(console_handler)
                    print(
                        f"CRITICAL: Failed to configure logging: {final_error}. Using manual console logging with redaction.",
                        file=sys.stderr,
                    )
                except Exception as critical_error:
                    print(
                        f"CRITICAL: Failed to create any logging handlers: {critical_error}. No logging available.",
                        file=sys.stderr,
                    )


setup_default_logging()
