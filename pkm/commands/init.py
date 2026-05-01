"""`pkm init` — placeholder. Real impl in Task 7."""
import typer

def register(app: typer.Typer) -> None:
    @app.command("init")
    def _stub() -> None:
        """(stub — implemented in M1 Task 7)"""
        raise NotImplementedError("init not implemented yet")
