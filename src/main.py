import web_server
import logging
import os
from twisted.python import log as twlog
import sys

def main():
    
    twlog.startLogging(sys.stdout)

    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'multifoundry.settings')
    logging.basicConfig(level=logging.NOTSET)
    web_server.run()

if __name__ == "__main__":
    main()