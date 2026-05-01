"""`pkm doctor` — placeholder. Real impl in Task 8."""
import typer

def register(app: typer.Typer) -> None:
    @app.command("doctor")
    def _stub() -> None:
        """(stub — implemented in M1 Task 8)"""
        raise NotImplementedError("doctor not implemented yet")
