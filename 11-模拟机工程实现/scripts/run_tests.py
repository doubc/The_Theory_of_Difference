import sys, os
os.chdir(r"C:\Users\Administrator\Documents\the_theory_of_difference\11-模拟机工程实现")
sys.argv = ["pytest", "tests/test_zone_transition.py", "-v", "--tb=short"]
import pytest
pytest.main()
