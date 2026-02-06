"""All models must be imported here so SQLAlchemy registers them."""

from app.models.core import Item, Connection, Snapshot  # noqa: F401
from app.models.infrastructure import User, Permission, Notification  # noqa: F401
