import httpx
from app.models import FileUploadCreate, FileUpload

if __name__ == "__main__":
    file_create = FileUploadCreate(
        filename="a.zip",
        file_size=10
    )
    with httpx.Client() as client:
        r = client.post("http://127.0.0.1:8000/file/create_upload_task", json=file_create.model_dump())
        file_upload = FileUpload.model_validate(r.json())
        ...