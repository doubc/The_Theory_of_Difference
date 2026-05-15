"""Test _get_symbols from daily_scan"""
import os
from sqlalchemy import create_engine, inspect

password = os.getenv('MYSQL_PASSWORD', '')
pwd_part = f":{password}" if password else ""
engine = create_engine(f"mysql+pymysql://root{pwd_part}@localhost/sina_futures?charset=utf8")
try:
    tables = inspect(engine).get_table_names()
    symbols = [t for t in tables if not t.endswith("m5") and not t.startswith("test")]
    print("Symbols:", len(symbols), symbols[:5])
except Exception as e:
    print("Error:", type(e).__name__, str(e)[:200])

# Test with no pwd_part (empty string)
engine2 = create_engine("mysql+pymysql://root@localhost/sina_futures?charset=utf8")
try:
    tables2 = inspect(engine2).get_table_names()
    symbols2 = [t for t in tables2 if not t.endswith("m5")]
    print("Without pwd_part:", len(symbols2), symbols2[:3])
except Exception as e:
    print("Engine2 error:", type(e).__name__, str(e)[:200])