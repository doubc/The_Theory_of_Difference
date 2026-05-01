@echo off
set MYSQL_PASSWORD=
cd /d "C:\Users\Administrator\source\repos\doubc\The_Theory_of_Difference\10-期货价格结构检索系统\price-structure\src\workbench"
python -c "import os; print('MYSQL_PASSWORD:', repr(os.environ.get('MYSQL_PASSWORD')))"
python -c "import os; os.environ['MYSQL_PASSWORD']=''; import sys; sys.path.insert(0,'..'); from data.loader import MySQLLoader; loader=MySQLLoader(); bars=loader.get('cu0','2026-04-20','2026-04-27','1d'); print('MySQL OK, bars:',len(bars))"
