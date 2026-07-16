from app.repositories.base import BaseRepository
from app.models.operation import Event


class EventRepository(BaseRepository):
    model = Event
