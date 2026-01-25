import streamlit as st
import pandas as pd
import os
import tempfile
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.validation import (
    detectar_encoding,
    detectar_delimitador,
    validar_csv_completo
)



