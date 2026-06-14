"""Test syntax of multi_world.py"""
import sys
sys.path.insert(0, r"C:\Users\Administrator\Documents\the_theory_of_difference\11-模拟机工程实现\engine_v2")
try:
    from diffsim.multi_world import MultiWorld
    print("OK: MultiWorld imported")
except SyntaxError as e:
    print(f"SYNTAX ERROR: {e}")
except Exception as e:
    print(f"ERROR: {e}")
