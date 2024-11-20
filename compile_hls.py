import os
import json
import sys
from cx_Freeze import setup, Executable

project_dir = os.path.dirname(os.path.abspath(__file__))

icon_path = os.path.join(project_dir, "icon.ico")

version_file = os.path.join(project_dir, "version.json")
with open(version_file, 'r', encoding='utf-8') as f:
    version_data = json.load(f)
    version = version_data.get('version', 'Unknown')

output_name = "HookLineSinker"

# Include files that need to be bundled
include_files = [
    ('icon.ico', 'icon.ico'),
    ('version.json', 'version.json'),
    ('GASecret.txt', 'GASecret.txt')
]

# Build options
build_options = {
    'packages': [],
    'excludes': [],
    'include_files': include_files
}

# Dist options
dist_options = {
    'bundle_name': output_name,
    'include_resources': include_files
}

# Create the executable
base = 'Win32GUI' if sys.platform == 'win32' else 'gui'
exe = Executable(
    "ui.py",
    base=base,
    icon=icon_path
)

# Run the setup
setup(
    name=output_name,
    version=version,
    description='Hook, Line, & Sinker Mod Manager',
    options={
      'build_exe': build_options,
      'bdist_mac': dist_options
    },
    executables=[exe]
)

print(f"Compilation complete. Executable created: {output_name}")