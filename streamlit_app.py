# -*- coding: utf-8 -*-
"""
Streamlit Community Cloud Primary Entrypoint (streamlit_app.py)
==============================================================
Loads and executes dashboard_app.py seamlessly.
"""
import runpy
from pathlib import Path

app_path = Path(__file__).parent / "dashboard_app.py"
runpy.run_path(str(app_path), run_name="__main__")
