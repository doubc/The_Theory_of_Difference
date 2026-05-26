#!/usr/bin/env python
"""Git status and commit"""
import os, subprocess, sys
os.chdir(os.path.dirname(os.path.abspath(__file__)))

result = subprocess.run(["git", "add", "-A"], capture_output=True, text=True)
result2 = subprocess.run(["git", "status", "--short"], capture_output=True, text=True)
print("Status:")
print(result2.stdout)

# Commit
result3 = subprocess.run(
    ["git", "commit", "-m", "fix(A3): enable locality violation measurement in L0 + reactor\n\n- L0BinaryLattice.locality_violation(): replace stub (always 0) with\n  actual non-local change detection via 3x3 pooling\n- reactor._compute_axiom_loss(): replace hardcoded A3=0 with real\n  computation using layer.locality_violation() + layer weight\n\nRoot cause: A3 locality was always 0 because both the layer method\nand reactor loss ignored it. This caused the system to diffuse instead\nof condense, as observed in heartbeat analysis 2026-05-26."],
    capture_output=True, text=True
)
print("Commit:", result3.stdout)
if result3.stderr:
    print("STDERR:", result3.stderr)
