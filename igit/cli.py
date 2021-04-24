"""Console script for igit."""
import sys
import igit
import click


@click.group()
def main():
    """Console script for igit."""
    click.echo("Replace this message by putting your code into "
               "igit.cli.main")
    click.echo("See click documentation at https://click.palletsprojects.com/")
    return 0

@main.command()
@click.option('--path', default="./", help='Path to repo.')
def serve(path):
    import uvicorn
    app = igit.server.make_app(path)
    uvicorn.run(app, host="0.0.0.0", port=5000, log_level="info")


if __name__ == "__main__":
    sys.exit(main())  # pragma: no cover
