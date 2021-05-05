from pydantic import BaseModel

from .models import User

class Config(BaseModel):
    user: User = None
    main_branch: str = "master"
    HEAD: str = main_branch
    root_path: str = "file://./"
    igit_path: str = ".igit"
    tree_path: str = None
    objects_path: str = "/".join([igit_path, "objects"])
    refs_path: str = "/".join([igit_path, "refs"])

    serializer: str = "msgpack-dill"
    hash_func: str = "sha1"
    compression: str = None
    encryption: str = None
