import os
import json
import sys
from cx_Freeze import setup, Executable

project_dir = os.path.dirname(os.path.abspath(__file__))

icon_path_win = os.path.join(project_dir, "icon.ico")
icon_path_mac = os.path.join(project_dir, "icon.icns")

version_file = os.path.join(project_dir, "version.json")
with open(version_file, 'r', encoding='utf-8') as f:
    version_data = json.load(f)
    version = version_data.get('version', 'Unknown')

raw_name = "HookLineSinker"
pretty_name = "Hook, Line, & Sinker"

# Include files that need to be bundled
include_files = [
    ('icon.ico', 'icon.ico'),
    ('icon.icns', 'icon.icns'),
    ('version.json', 'version.json')
]

# Build options
build_options = {
    'packages': [],
    'excludes': [],
    'include_files': include_files
}

# Dist options
dist_options = {
    'iconfile': icon_path_mac,
    'bundle_name': pretty_name,
    'include_resources': include_files
}

# Create the executable
exe = Executable(
    "ui.py",
    base='Win32GUI' if sys.platform == 'win32' else 'gui',
    icon=icon_path_win if sys.platform == 'win32' else icon_path_mac
)

# Run the setup
setup(
    name=raw_name,
    version=version,
    description='Hook, Line, & Sinker Mod Manager',
    options={
      'build_exe': build_options,
      'bdist_mac': dist_options
    },
    executables=[exe]
)

print(f"Compilation complete. Executable created: {pretty_name}")