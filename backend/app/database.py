from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from app.config import settings

# Create engine. Using pool_pre_ping=True prevents connection drops in long-running services.
engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def get_db():
    """Dependency injection helper to yield database sessions."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
