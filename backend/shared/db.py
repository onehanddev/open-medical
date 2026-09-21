from backend.api.config.get_env import db_url
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

if not db_url:
    raise RuntimeError(
        "DB_URL is missing. Add it to backend/.env "
        "or set it in the environment."
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