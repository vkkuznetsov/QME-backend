from pathlib import Path

from dynaconf import Dynaconf

PROJECT_PATH = Path(__file__).parent.resolve()

settings = Dynaconf(
    root_path=PROJECT_PATH,
    envvar_prefix='',
    environments=True,
    includes=["config/*.yml"]
)
