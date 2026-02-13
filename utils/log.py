# Copyright The IETF Trust 2024-2026, All Rights Reserved
"""JSON Logger Utilities"""

import logging
import time

from celery import current_task
from celery.app.log import TaskFormatter
from pythonjsonlogger.json import JsonFormatter as _JsonFormatter


class JsonFormatter(_JsonFormatter):
    """JSON formatter class with UTC timestamps and '.' decimal separators"""

    converter = time.gmtime  # use UTC
    default_msec_format = "%s.%03d"  # '.' instead of ','


class GunicornRequestJsonFormatter(JsonFormatter):
    """Only works with Gunicorn's logging"""

    def add_fields(self, log_data, record, message_dict):
        super().add_fields(log_data, record, message_dict)
        log_data.setdefault("method", record.args["m"])
        log_data.setdefault("proto", record.args["H"])
        log_data.setdefault("remote_ip", record.args["h"])
        path = record.args["U"]  # URL path
        if record.args["q"]:  # URL query string
            path = "?".join([path, record.args["q"]])
        log_data.setdefault("path", path)
        log_data.setdefault("status", record.args["s"])
        log_data.setdefault("referer", record.args["f"])
        log_data.setdefault("user_agent", record.args["a"])
        log_data.setdefault("len_bytes", record.args["B"])
        log_data.setdefault("duration_s", record.args["L"])  # decimal seconds
        log_data.setdefault("host", record.args["{host}i"])
        log_data.setdefault("x_request_start", record.args["{x-request-start}i"])
        log_data.setdefault("x_forwarded_for", record.args["{x-forwarded-for}i"])
        log_data.setdefault("x_forwarded_proto", record.args["{x-forwarded-proto}i"])
        log_data.setdefault("cf_connecting_ip", record.args["{cf-connecting-ip}i"])
        log_data.setdefault("cf_connecting_ipv6", record.args["{cf-connecting-ipv6}i"])
        log_data.setdefault("cf_ray", record.args["{cf-ray}i"])


class SimpleFormatter(logging.Formatter):
    converter = time.gmtime  # use UTC
    default_msec_format = "%s.%03d"  # "." instead of ","


class CeleryTaskFormatter(TaskFormatter):
    converter = time.gmtime  # use UTC
    default_msec_format = "%s.%03d"  # "." instead of ","


class CeleryTaskJsonFormatter(JsonFormatter):
    """JsonFormatter for tasks, adding the task name and id

    Based on celery.app.log.TaskFormatter
    """

    def format(self, record):
        task = current_task
        if task and task.request:
            record.__dict__.update(task_id=task.request.id, task_name=task.name)
        else:
            record.__dict__.setdefault("task_name", "???")
            record.__dict__.setdefault("task_id", "???")
        return super().format(record)
