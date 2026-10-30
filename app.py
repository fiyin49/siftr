"""SIFTR entry point: run with ``python -m streamlit run app.py``."""

import sys

# Keep imported application bytecode out of the course submission tree.
sys.dont_write_bytecode = True

from ui import main


if __name__ == "__main__":
    main()
