"""Services module."""

from .repositories import UserRepository
from .models import UserCreate, User


class UserService:
    def __init__(self, repo: UserRepository) -> None:
        self._repo = repo

    async def add(self, user: UserCreate) -> User:
        user = User.model_validate(user)
        return await self._repo.add(user)
