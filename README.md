# Postcode Parse

An application to manipulate postcode data (Windows ONLY).

## Requirements

- **Python 3**
- **Python virtual environment** - Setup a folder called `.venv` with `python -m venv .venv` and activate with `.\\.venv\\Scripts\\activate`
- **Dependencies** - Installed by running `pip install -e .[dev] --upgrade` (remember to do so from inside a virtual environment)
- **Setup Pre-commit hooks** - run `pre-commit install`

## Create Release

- Update version number
  - `pyproject.toml`
  - `postcode_parser.iss`
  - `src/postcode_parse/_version.py`

## Build Exe

- `pyinstaller --console --onefile src/postcode_parse/postcode_parse.py --clean --icon=assets/postcode.ico --distpath=./`
- Compile the `postcode_parser.iss` in Inno Setup Compiler
- Run the installer (to install or to update)

## Launching

- To launch via **Python**, call `python src/postcode_parse/postcode_parse.py` from within the virtual environment.
