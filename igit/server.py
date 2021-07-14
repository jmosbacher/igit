
import pathlib



TEMPLATE_DIR = pathlib.Path(__file__).parent.parent / "server_templates"

def make_app(path, prefix="repos"):
    from fastapi import FastAPI, Request
    from fastapi.responses import HTMLResponse
    from fastapi.staticfiles import StaticFiles
    from fastapi.templating import Jinja2Templates
    
    if not isinstance(path, pathlib.Path):
        path = pathlib.Path(path)
    path = path.expanduser()
    app = FastAPI()
    templates = Jinja2Templates(directory=TEMPLATE_DIR)

    app.mount(f"/igit/{prefix.strip('/')}/{path.name}", StaticFiles(directory=str(path)), name=path.name)

    @app.get(f"/igit/{prefix.strip('/')}/{path.name}", response_class=HTMLResponse)
    async def list_files(request: Request):
        paths = [f"/igit/{prefix.strip('/')}/{path.name}{str(p).replace(str(path), '')}" for p in path.rglob("*") if p.is_file()]
        return templates.TemplateResponse("index.html", {"request": request, "paths": paths})
    return app


# @app.get("/objects/{obj_id}")
# async def get_object(obj_id):
#     return {"obj_id": obj_id}

# @app.put("/objects/{obj_id}")
# async def put_object(obj_id):
#     return {"obj_id": obj_id}

# @app.post("/objects")
# async def post_objects(objs):
#     pass

# async def clone(repo_id):
#     pass

# async def fetch(repo_id, branch="master"):
#     pass

# async def push(repo_id, commit, branch="master"):
#     pass

