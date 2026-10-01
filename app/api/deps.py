from typing import Annotated

from fastapi import Depends
from sqlalchemy.orm import Session

from app.auth.dependencies import CurrentUserId
from app.db.database import get_db

DbSession = Annotated[Session, Depends(get_db)]

__all__ = ["CurrentUserId", "DbSession"]
