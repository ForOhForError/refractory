import web_server
import logging
import os

def main():
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'multifoundry.settings')
    logging.basicConfig(level=logging.NOTSET)
    web_server.run()

if __name__ == "__main__":
    main()