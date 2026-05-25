#!/usr/bin/env python
"""
Cleanup script - removes temporary setup files
These were used during development but are no longer needed
"""
import os

temp_files = [
    'create_dirs.py',
    'init_dirs.py',
    'run_setup.py',
    'setup_templates.py',
    'test_mkdir.py',
    'verify_setup.py',
    'SUBMISSION_SYSTEM_README.py',  # Replaced with markdown docs
]

base_dir = os.path.dirname(os.path.abspath(__file__))

print("Cleaning up temporary setup files...\n")

for filename in temp_files:
    filepath = os.path.join(base_dir, filename)
    if os.path.exists(filepath):
        try:
            os.remove(filepath)
            print(f"✓ Removed: {filename}")
        except Exception as e:
            print(f"✗ Failed to remove {filename}: {e}")
    else:
        print(f"- Skipped: {filename} (not found)")

print("\n✅ Cleanup complete!")
print("\nRemaining useful files:")
print("  ✓ submissions/      - Application package")
print("  ✓ templates/        - HTML templates (auto-generated)")
print("  ✓ SUBMISSION_SYSTEM_GUIDE.md - User guide")
print("  ✓ SUBMISSION_IMPLEMENTATION_CHANGELOG.md - Technical changelog")
print("  ✓ SUBMISSION_SYSTEM_COMPLETE.md - Implementation summary")
print("  ✓ verify_submission_system.py - Verification script")
