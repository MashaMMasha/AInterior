from sqlalchemy import create_engine, Engine

from obllomov.schemas.orm.chat import Base


def create_db_engine(url: str = "sqlite:///obllomov.db") -> Engine:
    engine = create_engine(url)
    # Таблицы создаются через init.sql в PostgreSQL, не создаём их здесь
    Base.metadata.create_all(engine)
    return engine
