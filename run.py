"""Entry point — run with:  python run.py"""
from app import create_app

app = create_app()

if __name__ == "__main__":
    # Auto-reload is great for source edits but breaks long-running
    # subprocesses that drop files into the project tree — CodeQL writes
    # temp files into ./codeql-db/ during `database create`, which the
    # reloader picks up and restarts on, killing the in-flight HTTP
    # request mid-build. Exclude DB output directories from the watch
    # set so reload still fires on real source edits.
    app.run(
        debug=True,
        port=5050,
        exclude_patterns=[
            "*/codeql-db/*",
            "*/codeql-db-*/*",
            "*/.venv/*",
            "*/node_modules/*",
            "*/__pycache__/*",
        ],
    )
