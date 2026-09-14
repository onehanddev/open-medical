from config.get_env import db_url
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

if not db_url:
    raise RuntimeError(
        "DB_URL is missing. Set it as an environment variable "
        "(Lambda console > Configuration > Environment variables) "
        "or in backend/worker/.env for local runs."
    )

engine = create_engine(db_url,
              pool_pre_ping= True,
              pool_size=5,
              max_overflow=5,
              connect_args={"connect_timeout": 15}
)

SessionLocal = sessionmaker(bind=engine)

class Base(DeclarativeBase):
    pass

def get_db():
    with SessionLocal() as session:
        yield session