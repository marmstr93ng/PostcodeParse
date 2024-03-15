# Postcode Parse

An application to manipulate postcode data.

## Requirements

- **Python 3**
- **Python virtual environment** - Setup a folder called `.venv` with `python -m venv .venv` and activate with `.\\.venv\\Scripts\\activate`
- **Dependencies** - Installed by running `pip install -e .[dev]` (remember to do so from inside a virtual environment)

## Build Exe

- `pyinstaller --onefile src/postcode_parse/postcode_parse.py`

## Launching

- To launch via **Python**, call `python src/postcode_parse/postcode_parse.py` from within the virtual environment.
