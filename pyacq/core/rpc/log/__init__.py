# -*- coding: utf-8 -*-
# Copyright (c) 2016, French National Center for Scientific Research (CNRS)
# Distributed under the (new) BSD License. See LICENSE for more info.

from .remote import (get_logger_address, set_logger_address, 
                     get_host_name, set_host_name,
                     get_process_name, set_process_name, 
                     get_thread_name, set_thread_name,
                     start_log_server, LogSender, LogServer)
from .handler import RPCLogHandler, log_exceptions
