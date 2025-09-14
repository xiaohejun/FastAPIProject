from fastapi import APIRouter, Depends

from app.api.deps import get_user_service
from app.models import UserCreate, User, FileUploadCreate, FileUpload
from app.services import UserService

users_router = APIRouter(
    prefix="/users",
    tags=["Admin/Users"],
)

@users_router.post("/add")
async def add(
    user: UserCreate,
    svc: UserService = Depends(get_user_service),
) -> User:
    print(f"user add begin")
    user = await svc.add(user)
    print(f"user add end")
    return user

# @users_router.post("/task")
# async def add(
#     user: UserCreate,
#     svc: UserService = Depends(get_user_service),
# ) -> User:
#     print(f"task begin")
#     user = await svc.add(user)
#     print(f"task end")
#     return user
#
items_router = APIRouter(
    prefix="/items",
    tags=["Admin/Items"],
)

@items_router.get("/get_all")
async def get_all():
    return {"message": "Hello World"}