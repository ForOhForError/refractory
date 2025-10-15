import logging
import os
import sys

from twisted.python import log, util
from twisted.python.log import FileLogObserver, _safeFormat, textFromEventDict

from refractory_settings import SERVER_PORT
from web_server import RefractoryServer

LOGGER = logging.getLogger("main")


class LogObserver(log.PythonLoggingObserver):
    def emit(self, eventDict):
        pass


def start_log():
    o = LogObserver()
    log.startLoggingWithObserver(o.emit)


def main():
    logging.basicConfig(level=logging.INFO)
    start_log()
    LOGGER.info(f"Running Refractory Server on port {SERVER_PORT}")
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "refractory.settings")
    RefractoryServer.get_server().run(port=SERVER_PORT)


if __name__ == "__main__":
    main()
