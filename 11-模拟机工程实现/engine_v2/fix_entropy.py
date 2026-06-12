"""Fix is_irreversible method in entropy.py."""
with open("diffsim/entropy.py", "r", encoding="utf-8") as f:
    lines = f.readlines()

# Find the is_irreversible method and fix it
in_method = False
fixed = False
for i, line in enumerate(lines):
    if "def is_irreversible" in line:
        in_method = True
        start_idx = i
    if in_method and "all(p > 0" in line:
        # Replace this line
        lines[i] = line.replace("all(p > 0", "any(abs(p) > 1e-10")
        fixed = True
        break

if fixed:
    with open("diffsim/entropy.py", "w", encoding="utf-8") as f:
        f.writelines(lines)
    print(f"Fixed is_irreversible method at line {start_idx+1}")
else:
    print("Method not found or already fixed")
    # Print lines around is_irreversible for debugging
    for i, line in enumerate(lines):
        if "is_irreversible" in line:
            print(f"  Line {i+1}: {line.rstrip()}")
            for j in range(i, min(i+7, len(lines))):
                print(f"  Line {j+1}: {lines[j].rstrip()}")
