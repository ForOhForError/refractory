import web_server
import logging

def main():
    logging.basicConfig(level=logging.NOTSET)
    web_server.run()

if __name__ == "__main__":
    main()