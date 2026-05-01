@echo off
set MYSQL_PASSWORD=
cd /d "C:\Users\Administrator\source\repos\doubc\The_Theory_of_Difference\10-期货价格结构检索系统\price-structure\src\workbench"
python -m streamlit run app.py --server.headless true --server.port 8516
