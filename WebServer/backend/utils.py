import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

try:
    from common import Logger
    log = Logger.instance()
except Exception as e:
    log = None
    print(f"Failed to initialize Logger: {str(e)}")