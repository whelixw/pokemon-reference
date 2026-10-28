"""Community Cloud entrypoint: both editions, saved data only."""
import os
from pathlib import Path
import runpy
import sys

os.environ['POKEMON_PUBLIC_MODE'] = '1'
directory = Path(__file__).resolve().parent
sys.path.insert(0, str(directory))
runpy.run_path(str(directory / 'app.py'), run_name='__main__')
