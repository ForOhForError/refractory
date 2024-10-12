import logging
import os
import sys

from web_server import RefractoryServer

from twisted.python import log, util
from twisted.python.log import FileLogObserver, textFromEventDict, _safeFormat

class LogObserver(FileLogObserver):
    def emit(self, eventDict):
        text = textFromEventDict(eventDict)
        if text is None:
            return
        util.untilConcludes(self.write, text+"\n")
        util.untilConcludes(self.flush)
        
def start_log():
    o = LogObserver(sys.stdout)
    log.startLoggingWithObserver(o.emit)

def main():
    
    #log.startLogging(sys.stdout)
    #start_log()

    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'refractory.settings')
    logging.basicConfig(level=logging.INFO)
    RefractoryServer.get_server().run()

if __name__ == "__main__":
    main()