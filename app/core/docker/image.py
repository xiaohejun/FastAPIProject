"""封装docker-py的镜像"""

from __future__ import annotations

from typing import Any

from pydantic_settings import BaseSettings
from pydantic import Field

class ImageSpec(BaseSettings):
    """
    Docker镜像规格
    """

    image: str
    # Keep the container alive between uses. Override if your image lacks /bin/sh.
    keepalive_command: list[str] = Field(
        default_factory=lambda: ["sleep", "infinity"]
    )  # e.g., ["sleep", "infinity"] or ["tail", "-f", "/dev/null"]
    env: dict[str, str] = Field(default_factory=dict)
    extra_run_kwargs: dict[str, Any] = Field(
        default_factory=dict
    )  # any additional docker.containers.run kwargs