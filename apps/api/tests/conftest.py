import os

os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["RAW_DATA_DIR"] = "data/test-raw"
