import logging
import logging.config
import json
import unittest
import os 
import sys

with open("logging.json", "r", encoding="utf-8") as f:
    config = json.load(f)
logging.config.dictConfig(config)

root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, root)

if __name__ == "__main__":
    suite = unittest.TestLoader().discover(start_dir=os.path.dirname(__file__), top_level_dir=root)
    unittest.TextTestRunner().run(suite)