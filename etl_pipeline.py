"""Entry point script.

This keeps the CLI simple: run the ETL that populates the SQLite warehouse.
Pandas analysis and visualisation now live in the notebook under `notebook/`.
"""

from Src.etl import run_etl


def main() -> None:
    run_etl()


if __name__ == "__main__":
    main()


