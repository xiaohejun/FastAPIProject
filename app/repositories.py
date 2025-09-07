"""Repositories module."""
from typing import Optional

from sqlmodel.ext.asyncio.session import AsyncSession

from .models import User


class UserRepository:
    def __init__(self, session: AsyncSession):
        assert isinstance(session, AsyncSession)
        print(f"repo get session {id(session)}")
        self.session = session

    # async def get_by_email(self, email: str) -> Optional[User]:
    #     res = await self.session
    #     return res.first()

    async def add(self, user: User) -> User:
        self.session.add(user)
        await self.session.flush()
        await self.session.refresh(user)
        return user