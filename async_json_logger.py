# async_json_logger.py

import logging
import os
import queue
from logging.handlers import RotatingFileHandler, QueueHandler, QueueListener
from pythonjsonlogger import jsonlogger


class AsyncJsonLogger:
    def __init__(
        self,
        name: str,
        log_file: str = "logs/app.log",
        level: int = logging.INFO,
        max_bytes: int = 5 * 1024 * 1024,
        backup_count: int = 3,
    ):
        self.name = name
        self.logger = logging.getLogger(name)
        self.logger.setLevel(level)

        if not self.logger.handlers:
            # Ensure log directory exists
            os.makedirs(os.path.dirname(log_file), exist_ok=True)

            # Queue for async logging
            self.log_queue = queue.Queue(-1)  # Infinite size

            # File handler (rotating)
            file_handler = RotatingFileHandler(
                log_file, maxBytes=max_bytes, backupCount=backup_count
            )
            file_handler.setFormatter(self._get_json_formatter())

            # # Console handler
            # console_handler = logging.StreamHandler()
            # console_handler.setFormatter(self._get_json_formatter())

            # Listener for async logging
            # self.listener = QueueListener(self.log_queue, file_handler, console_handler)
            self.listener = QueueListener(self.log_queue, file_handler)
            self.listener.start()

            # Queue handler pushes logs to queue
            queue_handler = QueueHandler(self.log_queue)
            self.logger.addHandler(queue_handler)

    def _get_json_formatter(self):
        return jsonlogger.JsonFormatter(
            fmt='%(asctime)s %(levelname)s %(name)s %(funcName)s %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )

    def get_logger(self):
        return self.logger

    def stop(self):
        """Call this before exiting your program to flush and stop the listener."""
        self.listener.stop()
