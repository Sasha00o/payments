from decimal import Decimal

from app.repositories.base import BaseRepository
from app.models.operation import Operation, Event
from app.constants import EventType, OperationStatus
from app.core.database.engine import async_session_maker


class OperationRepository(BaseRepository):
    model = Operation

    @classmethod
    async def create_with_event(
        cls,
        operation_id: str,
        amount: Decimal,
        currency: str,
        description: str | None,
    ) -> Operation:
        """
        Атомарное создание операции с событием CREATED
        """
        async with async_session_maker() as session:
            async with session.begin():
                operation = Operation(
                    id=operation_id,
                    amount=amount,
                    currency=currency,
                    description=description,
                    status=OperationStatus.CREATED,
                )
                session.add(operation)

                event = Event(
                    operation_id=operation_id,
                    event_type=EventType.CREATED,
                    from_status=None,
                    to_status=OperationStatus.CREATED,
                )
                session.add(event)

                await session.flush()
                await session.refresh(operation)

        return operation
