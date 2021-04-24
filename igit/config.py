from pydantic import BaseModel

from .models import User

class Config(BaseModel):
    user: User
