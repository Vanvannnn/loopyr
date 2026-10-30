import os, sys

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path[:0] = [RACINE, os.path.dirname(os.path.abspath(__file__))]
