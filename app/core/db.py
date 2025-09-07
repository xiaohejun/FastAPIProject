from contextlib import asynccontextmanager, AbstractAsyncContextManager
from typing import AsyncGenerator
from sqlmodel import SQLModel
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlmodel.ext.asyncio.session import AsyncSession
from uuid import UUID

from app.models import User

class Database(AbstractAsyncContextManager):
    def __init__(
        self,
        url: str,
        *,
        pool_size: int = 20,
        max_overflow: int = 10,
        pool_recycle: int = 1800,
        echo: bool = False
    ):
        # 异步引擎配置
        self.engine = create_async_engine(url, pool_size=pool_size,
                                          max_overflow=max_overflow, pool_recycle=pool_recycle, echo=echo)
        self.session_factory = async_sessionmaker(bind=self.engine, class_=AsyncSession, expire_on_commit=False)

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        print("Closing database connection")
        await self.disconnect()

    async def disconnect(self) -> None:
        """关闭所有数据库连接"""
        if self.engine:
            await self.engine.dispose()

    @asynccontextmanager
    async def scope_session(self) -> AsyncGenerator[AsyncSession, None]:
        """推荐直接返回 AsyncSession 类型"""
        session = self.session_factory()
        print(f"get session {id(session)}")
        try:
            print(f"yield session {id(session)}")
            yield session
            print(f"commit session {id(session)}")
            await session.commit()
        except Exception as e:
            print(f"error {e}")
            await session.rollback()
            raise
        finally:
            print(f"finished {id(session)}")
            await session.close()

    async def create_all(self):
        async with self.engine.begin() as conn:  # type: ignore
            await conn.run_sync(SQLModel.metadata.create_all)


if __name__ == "__main__":
    print("=====================")

    DB = Database(db_url="sqlite+aiosqlite:///testing.db")

    async def test_db():
        await DB.create_all()

        async def test_user_db():
            user = User(
                name="testuser",
                password="124"
            )
            print("=== user info: " + str(user) + "\n")
            print(hex(id(user)))

            async def test_create_user(user: User) -> User:
                async with DB.scope_session() as session:
                    session.add(user)
                    await session.commit()
                    await session.refresh(user)
                    print("=== user info after create: " + str(user) + "\n")
                    print(hex(id(user)))
                    return user.model_copy(deep=True)

            user = await test_create_user(user)
            print(hex(id(user)))

            print("=== user after created:\n" + str(user) + "\n")

            async def test_get_user(id: UUID):
                async with DB.scope_session() as session:
                    user = await session.get(User, id)
                    return user.model_copy(deep=True) if user else None
            await test_get_user(user.id)
            print("=== get user info:\n" + str(user) + "\n")

            async def test_update_user(user: User) -> User:
                async with DB.scope_session() as session:
                    user = await session.get(User, user.id)
                    if user:
                        user.name = "testuser2"
                        await session.commit()
                        await session.refresh(user)
                    return user.model_copy(deep=True)
            user = await test_update_user(user)
            print("=== user after updated:\n" + str(user) + "\n")

            async def test_delete_user(id: UUID):
                async with DB.scope_session() as session:
                    user = await session.get(User, id)
                    if user:
                        await session.delete(user)
                        await session.commit()
                        print("=== user deleted successfully")
                    else:
                        print("=== user not found")

            user = await test_get_user(user.id)
            print("=== user before deleted:\n" + str(user) + "\n")

            await test_delete_user(user.id)

            user = await test_get_user(user.id)
            print("=== user after deleted:\n" + str(user) + "\n")

        await test_user_db()
        print("=====================")

    import asyncio
    asyncio.run(test_db())