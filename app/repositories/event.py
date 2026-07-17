from sqlalchemy import select

from app.repositories.base import BaseRepository
from app.models.operation import Event
from app.core.database.engine import async_session_maker


class EventRepository(BaseRepository):
    model = Event

    @classmethod
    async def get_operation_events(cls, operation_id: str) -> list[Event]:
        """
        Получение всех событий операции, отсортированных по event_id
        """
        async with async_session_maker() as session:
            stmt = (
                select(Event)
                .where(Event.operation_id == operation_id)
                .order_by(Event.event_id.asc())
            )
            result = await session.execute(stmt)
            events = list(result.scalars().all())
            if not events:
                raise ValueError(
                    f'Events for this operation {operation_id} not found')
            return events
