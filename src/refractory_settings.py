import os
import logging

MANAGEMENT_PATH = "refractory"
INSTANCE_PATH = "instances"
MANAGED = True
NICENESS = "nice"

SERVER_PORT_ENV_VAR = "REFRACTORY_SERVER_PORT"
SERVER_PORT_DEFAULT = 8080
INITIAL_ADMIN_USERNAME_ENV_VAR = "REFRACTORY_INITIAL_ADMIN_USERNAME"
INITIAL_ADMIN_USERNAME_DEFAULT = None
INITIAL_ADMIN_PASSWORD_ENV_VAR = "REFRACTORY_INITIAL_ADMIN_PASSWORD"
INITIAL_ADMIN_PASSWORD_DEFAULT = None


def get_env_as_int(env_var: str, default: int):
    try:
        return int(os.getenv(env_var, default))
    except ValueError:
        logging.warning(
            f"Env var {env_var} was not an int value; defaulting to {default}"
        )
        return default


SERVER_PORT = get_env_as_int(SERVER_PORT_ENV_VAR, SERVER_PORT_DEFAULT)
INITIAL_ADMIN_USERNAME = os.getenv(
    INITIAL_ADMIN_USERNAME_ENV_VAR, INITIAL_ADMIN_USERNAME_DEFAULT
)
INITIAL_ADMIN_PASSWORD = os.getenv(
    INITIAL_ADMIN_PASSWORD_ENV_VAR, INITIAL_ADMIN_PASSWORD_DEFAULT
)
