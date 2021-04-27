
from .base import BaseObject
import getpass


class User(BaseObject):
    username: str
    email: str = ""

    @classmethod
    def get_user(cls, username=None, email=None):
        if username is None:
            username = getpass.getuser()
        if email is None:
            email = f"{username}@example.com"
        return cls(username=username, email=email)