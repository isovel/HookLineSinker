# standard library imports
import ctypes
import html.parser
import inspect
import io
import json
import os
import stat
import platform
import queue
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import traceback
import webbrowser
import zipfile
from urllib.parse import urlparse
import argparse
from packaging import version
import psutil
from datetime import datetime, timedelta, timezone
import logging
import random
import uuid

# third-party imports
import appdirs
import requests
import tkinter as tk
from dotenv import load_dotenv
from PIL import Image, ImageTk
from tkinter import ttk, filedialog, messagebox

# created by pyoid for more information visit the github repository
# small portions of this code were developed with assistance from anthropic's claude 3.5 sonnet
# if you need support ping me on discord @pyoid

load_dotenv()

# class to redirect logging output to a custom writer
class LoggerWriter:
    def __init__(self, level):
        self.level = level

    def write(self, message):
        if message != '\n':
            self.level(message)

    def flush(self):
        pass

# html parser to strip tags from text
class MLStripper(html.parser.HTMLParser):
    def __init__(self):
        super().__init__()
        self.reset()
        self.strict = False
        self.convert_charrefs= True
        self.text = []
    
    def handle_data(self, d):
        self.text.append(d)
    
    def get_data(self):
        return ''.join(self.text)

# removes html tags from a string
def strip_tags(html):
    s = MLStripper()
    s.feed(html)
    return s.get_data()

# retrieves the current version of the application
def get_version():
        if getattr(sys, 'frozen', False):
            # running as compiled executable
            bundle_dir = sys._MEIPASS
        else:
            # running in a normal python environment
            bundle_dir = os.path.dirname(os.path.abspath(__file__))
        
        version_file = os.path.join(bundle_dir, 'version.json')
        
        try:
            with open(version_file, 'r') as f:
                version_data = json.load(f)
                return version_data.get('version', 'Unknown')
        except Exception as e:
            logging.info(f"Error reading version file: {e}")
            return 'Unknown'

# main class for the hook line sinker user interface
class HookLineSinkerUI:
    def __init__(self, root):
        print("Initializing HookLineSinkerUI...")
        self.root = root
        print(f"Root window created: {root}")
        
        self.app_data_dir = appdirs.user_data_dir("Hook_Line_Sinker", "PyoidTM")
        print(f"App data directory: {self.app_data_dir}")
        
        print("Setting up logging...")
        self.setup_logging()
        print("Logging setup complete")
        
        print("Initializing queues...")
        self.gui_queue = queue.Queue()
        self.gdweave_queue = queue.Queue()
        print("Queues initialized")
        
        print("Loading settings...")
        self.load_settings()
        print("Settings loaded")
        
        print("Getting version...")
        version = get_version()
        print(f"Current version: {version}")

        print("Setting up window title and state...")
        self.root.title(f"Hook, Line, & Sinker v{version} - WEBFISHING Mod Manager")
        if not self.settings.get('windowed_mode', True):
            print("Fullscreen mode enabled")
            self.root.state('zoomed')
        else:
            print("Windowed mode enabled")
            # temporary test may get removed next update

            # get screen width and height
            screen_width = self.root.winfo_screenwidth()
            screen_height = self.root.winfo_screenheight()
            print(f"Screen dimensions: {screen_width}x{screen_height}")
            
            # set window dimensions
            window_width = 800
            window_height = 630
            print(f"Window dimensions: {window_width}x{window_height}")
            
            # calculate center position
            x = (screen_width - window_width) // 2
            y = (screen_height - window_height) // 2
            print(f"Window position: {x},{y}")
            
            # set window geometry
            self.root.geometry(f"{window_width}x{window_height}+{x}+{y}")

        print("Setting minimum window size...")
        self.root.minsize(800, 630)

        print("Loading application icon...")
        icon_path = os.path.join(os.path.dirname(__file__), 'icon.ico')
        print(f"Icon path: {icon_path}")
        if os.path.exists(icon_path):
            print("Icon file found")
            if platform.system() == 'Windows':
                print("Setting Windows icon")
                self.root.iconbitmap(icon_path)
            elif platform.system() == 'Linux':
                print("Setting Linux icon")
                img = tk.PhotoImage(file=icon_path)
                self.root.tk.call('wm', 'iconphoto', self.root._w, img)
        else:
            print("Warning: icon.ico not found")
            logging.info("Warning: icon.ico not found")
            
        print("Setting up mod directories...")
        self.app_data_dir = appdirs.user_data_dir("Hook_Line_Sinker", "PyoidTM")
        self.mods_dir = os.path.join(self.app_data_dir, "mods")
        self.mod_cache_file = os.path.join(self.app_data_dir, "mod_cache.json")
        print(f"Mods directory: {self.mods_dir}")
        print(f"Mod cache file: {self.mod_cache_file}")
        os.makedirs(self.mods_dir, exist_ok=True)
        print("Mod directories created")

        print("Initializing mod lists...")
        self.available_mods = []
        self.installed_mods = []
        print("Mod lists initialized")
        
        # mod category constants
        TOOLS = "Tools"
        COSMETICS = "Cosmetics"
        LIBRARIES = "Libraries"
        MODS = "Mods"
        MISC = "Misc"

        self.mod_categories = {}  # Will be populated dynamically from Thunderstore categories
                
        self.load_mod_cache()
        self.mod_downloading = False

        # initialize attributes
        self.windowed_mode = tk.BooleanVar(value=self.settings.get('windowed_mode', True))
        self.auto_update = tk.BooleanVar(value=self.settings.get('auto_update', True))
        self.notifications = tk.BooleanVar(value=self.settings.get('notifications', False))
        self.theme = tk.StringVar(value=self.settings.get('theme', 'System'))
        self.show_nsfw = tk.BooleanVar(value=self.settings.get('show_nsfw', False))
        self.show_deprecated = tk.BooleanVar(value=self.settings.get('show_deprecated', False))
        self.game_path_entry = tk.StringVar(value=self.settings.get('game_path', ''))

        logging.info(f"Initial game path: {self.game_path_entry.get()}")

        # create status bar
        self.create_status_bar()

        # initialize notebook
        self.notebook = None

        self.create_main_ui()

        # check for updates on startup and show discord prompt
        self.check_for_fresh_update()
        self.show_discord_prompt()
        self.check_for_duplicate_mods()

        # check for updates silently after 5 seconds removed
        if self.auto_update.get():
            self.check_for_updates(silent=True)
        else:
            self.check_for_program_updates()
            logging.info("Auto update is disabled, not prompting for any updates or program updates")

        # check if this is a fresh update
        parser = argparse.ArgumentParser()
        parser.add_argument('--fresh-update', action='store_true')
        args = parser.parse_args()

        if args.fresh_update:
            self.show_update_complete()

        # start update checking thread
        self.update_thread = threading.Thread(target=self.periodic_update_check, daemon=True)
        self.update_thread.start()
    # sets up logging to write to latestlog.txt and fulllatestlog.txt
    def setup_logging(self):
        print("Setting up logging system...")
        print(f"App data directory: {self.app_data_dir}")
        
        # ensure the directory exists
        log_dir = os.path.dirname(os.path.join(self.app_data_dir, 'latestlog.txt'))
        print(f"Creating log directory: {log_dir}")
        os.makedirs(log_dir, exist_ok=True)
        print("Log directory created/verified")
        
        # set up error-only logging to latestlog.txt
        error_log = os.path.join(self.app_data_dir, 'latestlog.txt')
        print(f"Setting up error log at: {error_log}")
        with open(error_log, 'w') as f:
            print("Writing error log header...")
            f.write("=" * 80 + "\n")
            f.write("Hook, Line, & Sinker Error Log\n")
            f.write("If you need support, join discord.gg/webfishingmods\n")
            f.write("This log only contains errors and important messages\n")
            f.write("=" * 80 + "\n\n")
        print("Error log header written")
        
        print("Configuring error log handler...")
        error_handler = logging.FileHandler(error_log, mode='a')
        error_handler.setLevel(logging.ERROR)
        error_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s', '%Y-%m-%d %H:%M:%S'))
        print("Error log handler configured")
        
        # set up full logging to fulllatestlog.txt
        full_log = os.path.join(self.app_data_dir, 'fulllatestlog.txt')
        print(f"Setting up full debug log at: {full_log}")
        with open(full_log, 'w') as f:
            print("Writing full log header...")
            f.write("=" * 80 + "\n")
            f.write("Hook, Line, & Sinker Full Debug Log\n")
            f.write("If you need support, join discord.gg/webfishingmods\n")
            f.write("This log contains all debug messages and program activity\n")
            f.write("=" * 80 + "\n\n")
        print("Full log header written")
        
        print("Configuring full log handler...")
        full_handler = logging.FileHandler(full_log, mode='a')
        full_handler.setLevel(logging.DEBUG)
        full_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s', '%Y-%m-%d %H:%M:%S'))
        print("Full log handler configured")
        
        # configure root logger
        print("Configuring root logger...")
        root_logger = logging.getLogger()
        root_logger.setLevel(logging.DEBUG)
        root_logger.addHandler(error_handler)
        root_logger.addHandler(full_handler)
        print("Root logger configured with both handlers")
        
        # redirect stdout and stderr
        print("Redirecting stdout and stderr to logging system...")
        sys.stdout = LoggerWriter(logging.info)
        sys.stderr = LoggerWriter(logging.error)
        print("Logging system setup complete!")

    # opens the latest log file in a new window
    def open_latest_log(self):
        log_path = os.path.join(self.app_data_dir, 'latestlog.txt')
        if os.path.exists(log_path):
            with open(log_path, 'r') as f:
                log_content = f.read()
            
            # create a new top-level window
            log_window = tk.Toplevel(self.root)
            log_window.title("HLS Log")
            log_window.geometry("800x600")
            
            # set the window icon
            icon_path = os.path.join(os.path.dirname(__file__), 'icon.ico')
            if os.path.exists(icon_path):
                log_window.iconbitmap(icon_path)

            # create main frame
            main_frame = ttk.Frame(log_window)
            main_frame.pack(expand=True, fill='both', padx=5, pady=5)
            main_frame.grid_columnconfigure(0, weight=1)
            main_frame.grid_rowconfigure(0, weight=1)

            # create text widget with scrollbar
            text_frame = ttk.Frame(main_frame)
            text_frame.grid(row=0, column=0, sticky='nsew')
            text_frame.grid_columnconfigure(0, weight=1)
            text_frame.grid_rowconfigure(0, weight=1)

            log_text = tk.Text(text_frame, wrap=tk.NONE, font=('Consolas', 10))
            log_text.grid(row=0, column=0, sticky='nsew')

            scrollbar = ttk.Scrollbar(text_frame, orient='vertical', command=log_text.yview)
            scrollbar.grid(row=0, column=1, sticky='ns')
            log_text.config(yscrollcommand=scrollbar.set)

            # create button frame
            button_frame = ttk.Frame(main_frame)
            button_frame.grid(row=1, column=0, sticky='ew', pady=(5, 0))
            button_frame.grid_columnconfigure(1, weight=1)

            # add buttons
            ttk.Button(button_frame, text="Refresh", command=lambda: self.refresh_log_content(log_text)).grid(row=0, column=0, padx=(0, 5))
            ttk.Button(button_frame, text="Copy to Clipboard", command=lambda: self.root.clipboard_append(log_text.get("1.0", tk.END))).grid(row=0, column=1)
            ttk.Button(button_frame, text="Close", command=log_window.destroy).grid(row=0, column=2)

            # insert the log content
            log_text.insert(tk.END, log_content)
            log_text.config(state='disabled')  # make the text read-only
        else:
            messagebox.showerror("Error", "Latest log file not found.")

    # opens the full log file in a new window
    def open_full_log(self):
        log_path = os.path.join(self.app_data_dir, 'fulllatestlog.txt')
        if os.path.exists(log_path):
            with open(log_path, 'r') as f:
                log_content = f.read()
            
            # create a new top-level window
            log_window = tk.Toplevel(self.root)
            log_window.title("Full HLS Log")
            log_window.geometry("800x600")
            
            # set the window icon
            icon_path = os.path.join(os.path.dirname(__file__), 'icon.ico')
            if os.path.exists(icon_path):
                log_window.iconbitmap(icon_path)

            # create main frame
            main_frame = ttk.Frame(log_window)
            main_frame.pack(expand=True, fill='both', padx=5, pady=5)
            main_frame.grid_columnconfigure(0, weight=1)
            main_frame.grid_rowconfigure(0, weight=1)

            # create text widget with scrollbar
            text_frame = ttk.Frame(main_frame)
            text_frame.grid(row=0, column=0, sticky='nsew')
            text_frame.grid_columnconfigure(0, weight=1)
            text_frame.grid_rowconfigure(0, weight=1)

            log_text = tk.Text(text_frame, wrap=tk.NONE, font=('Consolas', 10))
            log_text.grid(row=0, column=0, sticky='nsew')

            scrollbar = ttk.Scrollbar(text_frame, orient='vertical', command=log_text.yview)
            scrollbar.grid(row=0, column=1, sticky='ns')
            log_text.config(yscrollcommand=scrollbar.set)

            # create button frame
            button_frame = ttk.Frame(main_frame)
            button_frame.grid(row=1, column=0, sticky='ew', pady=(5, 0))
            button_frame.grid_columnconfigure(1, weight=1)

            # add buttons
            ttk.Button(button_frame, text="Refresh", command=lambda: self.refresh_log_content(log_text)).grid(row=0, column=0, padx=(0, 5))
            ttk.Button(button_frame, text="Copy to Clipboard", command=lambda: self.root.clipboard_append(log_text.get("1.0", tk.END))).grid(row=0, column=1)
            ttk.Button(button_frame, text="Close", command=log_window.destroy).grid(row=0, column=2)

            # insert the log content
            log_text.insert(tk.END, log_content)
            log_text.config(state='disabled')  # make the text read-only
        else:
            messagebox.showerror("Error", "Full log file not found.")
    
    # checks if the game is currently running (removed due to privacy concerns)

    # checks if the game is not running and shows an error if it is (removed due to privacy concerns)

    # checks for a fresh update and shows a message if one is found
    def check_for_fresh_update(self):
        current_version = version.parse(get_version())
        if last_update_version := self.settings.get('last_update_version'):
            last_update_version = version.parse(last_update_version)
            if current_version > last_update_version:
                messagebox.showinfo("Update Complete", f"Hook, Line, & Sinker has been updated to version {current_version}.")
                self.settings['last_update_version'] = str(current_version)
                self.save_settings()

    # toggles gdweave on or off
    # i need to implement checks to see if gdweave is toggled and disallow things like installing mods etc (1.2.1)
    def toggle_gdweave(self):
        if not self.settings.get('game_path'):
            messagebox.showerror("Error", "Game path not set. Please set the game path first.")
            return

        game_path = self.settings['game_path']
        gdweave_game_path = os.path.join(game_path, 'GDWeave')
        winmm_game_path = os.path.join(game_path, 'winmm.dll')
        
        gdweave_backup_path = os.path.join(self.app_data_dir, 'GDWeave_Backup')
        winmm_backup_path = os.path.join(self.app_data_dir, 'winmm_backup.dll')

        if os.path.exists(gdweave_game_path) or os.path.exists(winmm_game_path):
            # gdweave is currently in the game folder let's move it to backup
            try:
                if os.path.exists(gdweave_game_path):
                    shutil.move(gdweave_game_path, gdweave_backup_path)
                if os.path.exists(winmm_game_path):
                    shutil.move(winmm_game_path, winmm_backup_path)
                messagebox.showinfo("Success", "GDWeave has been disabled and backed up.")
                self.set_status("GDWeave disabled and backed up")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to disable GDWeave: {str(e)}")
                return
        else:
            # gdweave is not in the game folder let's restore it from backup
            try:
                if os.path.exists(gdweave_backup_path):
                    shutil.move(gdweave_backup_path, gdweave_game_path)
                if os.path.exists(winmm_backup_path):
                    shutil.move(winmm_backup_path, winmm_game_path)
                messagebox.showinfo("Success", "GDWeave has been enabled and restored.")
                self.set_status("GDWeave enabled and restored")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to enable GDWeave: {str(e)}")
                return

        self.update_toggle_gdweave_button()
        self.update_setup_status()

    # uninstalls gdweave
    def uninstall_gdweave(self):
        if not self.settings.get('game_path'):
            messagebox.showerror("Error", "Game path not set. Please set the game path first.")
            return

        gdweave_path = os.path.join(self.settings['game_path'], 'GDWeave')
        winmm_path = os.path.join(self.settings['game_path'], 'winmm.dll')
        
        if not os.path.exists(gdweave_path) and not os.path.exists(winmm_path):
            messagebox.showinfo("Info", "GDWeave is not installed.")
            return

        if messagebox.askyesno("Confirm Uninstall", "Are you sure you want to uninstall GDWeave? This will remove the GDWeave folder, all mods within it, and the winmm.dll file from your game directory."):
            try:
                # attempt to remove gdweave folder and winmmdll without elevation
                shutil.rmtree(gdweave_path, ignore_errors=True)
                if os.path.exists(winmm_path):
                    os.remove(winmm_path)

                # check if files still exist
                remaining_files = []
                if os.path.exists(gdweave_path):
                    remaining_files.append("GDWeave folder")
                if os.path.exists(winmm_path):
                    remaining_files.append("winmm.dll")
                
                if remaining_files:
                    # some files couldn't be deleted, possibly due to permissions or open programs
                    warning_message = f"Some files could not be deleted: {', '.join(remaining_files)}. This may be due to insufficient permissions or open programs. Please close all related programs and try again."
                    messagebox.showwarning("Partial Uninstall", warning_message)
                    self.set_status("GDWeave partially uninstalled")
                else:
                    # uninstall successful, update settings and ui
                    self.settings['gdweave_version'] = None
                    self.save_settings()
                    self.set_status("GDWeave uninstalled successfully")
                    messagebox.showinfo("Success", "GDWeave has been uninstalled successfully.")
                
                # refresh ui elements
                self.update_setup_status()
                self.update_toggle_gdweave_button()
                logging.info("GDWeave uninstallation process completed.")

            except Exception as e:
                # handle any unexpected errors during uninstallation
                error_message = f"Failed to uninstall GDWeave: {str(e)}"
                self.set_status(error_message)
                messagebox.showerror("Error", error_message)

    def create_main_ui(self):
        # create and set up the main user interface
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(expand=True, fill='both')

        # create various tabs for different functionalities
        self.create_mod_manager_tab()
        self.create_game_manager_tab()
        self.create_hls_setup_tab()
        self.create_settings_tab()
        
        # initialize mod-related functions
        self.copy_existing_gdweave_mods()
        self.load_available_mods()
        self.refresh_mod_lists()
    def create_mod_manager_tab(self):
        # create the mod manager tab for managing game modifications
        mod_manager_frame = ttk.Frame(self.notebook)
        self.notebook.add(mod_manager_frame, text="Mod Manager")

        # configure grid layout
        mod_manager_frame.grid_columnconfigure(0, weight=1)
        mod_manager_frame.grid_columnconfigure(1, weight=0)
        mod_manager_frame.grid_columnconfigure(2, weight=1)
        mod_manager_frame.grid_rowconfigure(0, weight=3)
        mod_manager_frame.grid_rowconfigure(1, weight=1)

        # create left panel for available mods
        available_frame = ttk.LabelFrame(mod_manager_frame, text="Available Mods")
        available_frame.grid(row=0, column=0, padx=5, pady=5, sticky="nsew")

        # create filter frame with better organization
        filter_frame = ttk.LabelFrame(available_frame, text="Filter Options")
        filter_frame.grid(row=0, column=0, sticky="ew", padx=2, pady=2)

        # create search frame
        search_frame = ttk.Frame(filter_frame)
        search_frame.pack(fill="x", padx=5, pady=2)

        ttk.Label(search_frame, text="Search:").pack(side="left", padx=5)
        self.search_var = tk.StringVar()
        self.search_var.trace('w', lambda name, index, mode: self.filter_available_mods())
        search_entry = ttk.Entry(search_frame, textvariable=self.search_var)
        search_entry.pack(side="left", fill="x", expand=True, padx=5)

        # create category frame
        category_frame = ttk.Frame(filter_frame)
        category_frame.pack(fill="x", padx=5, pady=2)

        ttk.Label(category_frame, text="Category:").pack(side="left", padx=5)
        self.available_category = ttk.Combobox(category_frame, state="readonly")
        self.available_category.pack(side="left", fill="x", expand=True, padx=5)
        self.available_category.bind('<<ComboboxSelected>>', lambda e: self.filter_available_mods())

        # create separate frame for toggles
        toggle_frame = ttk.Frame(filter_frame)
        toggle_frame.pack(fill="x", padx=5, pady=2)

        # they look like this so i can debug easier lmao
        ttk.Checkbutton(toggle_frame, text="Show NSFW", 
                       variable=self.show_nsfw,
                       command=lambda: self.handle_filter_toggle('nsfw')
        ).pack(side="left", padx=5)

        ttk.Checkbutton(toggle_frame, text="Show Deprecated",
                       variable=self.show_deprecated,
                       command=lambda: self.handle_filter_toggle('deprecated')
        ).pack(side="left", padx=5)

        # create listbox for available mods with scrollbar
        self.available_listbox = tk.Listbox(available_frame, width=30, height=15, selectmode=tk.EXTENDED)
        self.available_listbox.grid(row=1, column=0, pady=2, padx=2, sticky="nsew")
        self.available_listbox.bind('<<ListboxSelect>>', self.on_available_listbox_select)
        self.available_listbox.bind('<Button-3>', self.show_context_menu)

        # add scrollbar
        scrollbar = ttk.Scrollbar(available_frame, orient="vertical", command=self.available_listbox.yview)
        scrollbar.grid(row=1, column=1, sticky="ns")
        self.available_listbox.configure(yscrollcommand=scrollbar.set)

        available_frame.grid_columnconfigure(0, weight=1)
        available_frame.grid_rowconfigure(1, weight=1)

        # create middle panel for action buttons
        action_frame = ttk.Frame(mod_manager_frame)
        action_frame.grid(row=0, column=1, padx=5, pady=5, sticky="ns")

        action_frame.grid_rowconfigure(0, weight=1)
        action_frame.grid_rowconfigure(6, weight=1)

        # create game management section
        game_management_frame = ttk.LabelFrame(action_frame, text="Game Management")
        game_management_frame.grid(row=1, column=0, pady=5, padx=5, sticky="ew")
        game_management_frame.grid_columnconfigure(0, weight=1)
        ttk.Button(game_management_frame, text="Start Game", command=self.toggle_game).grid(row=0, column=0, pady=2, padx=2, sticky="ew")

        # create mod management section
        mod_management_frame = ttk.LabelFrame(action_frame, text="Mod Management")
        mod_management_frame.grid(row=2, column=0, pady=5, padx=5, sticky="ew")
        mod_management_frame.grid_columnconfigure(0, weight=1)
        mod_management_frame.grid_columnconfigure(1, weight=1)
        ttk.Button(mod_management_frame, text="Install", command=self.install_mod).grid(row=0, column=0, pady=2, padx=2, sticky="ew")
        ttk.Button(mod_management_frame, text="Uninstall", command=self.uninstall_mod).grid(row=0, column=1, pady=2, padx=2, sticky="ew")
        ttk.Button(mod_management_frame, text="Enable", command=self.enable_mod).grid(row=1, column=0, pady=2, padx=2, sticky="ew")
        ttk.Button(mod_management_frame, text="Disable", command=self.disable_mod).grid(row=1, column=1, pady=2, padx=2, sticky="ew")
        ttk.Button(mod_management_frame, text="Edit Config", command=self.edit_mod_config).grid(row=2, column=0, columnspan=2, pady=2, padx=2, sticky="ew")

        # create 3rd party mods section
        third_party_frame = ttk.LabelFrame(action_frame, text="3rd Party Mods")
        third_party_frame.grid(row=3, column=0, pady=5, padx=5, sticky="ew")
        third_party_frame.grid_columnconfigure(0, weight=1)
        third_party_frame.grid_columnconfigure(1, weight=1)
        ttk.Button(third_party_frame, text="Import ZIP", command=self.import_zip_mod).grid(row=0, column=0, padx=2, pady=2, sticky="ew")
        ttk.Button(third_party_frame, text="Refresh Mods", command=self.refresh_all_mods).grid(row=0, column=1, padx=2, pady=2, sticky="ew")
        ttk.Button(third_party_frame, text="View Deprecated Mods List", command=self.view_deprecated_mods_list).grid(row=1, column=0, columnspan=2, padx=2, pady=2, sticky="ew")

        # create help section
        help_frame = ttk.LabelFrame(action_frame, text="Need Help?")
        help_frame.grid(row=4, column=0, pady=5, padx=5, sticky="ew")
        help_frame.grid_columnconfigure(0, weight=1)
        help_frame.grid_columnconfigure(1, weight=1)
        ttk.Button(help_frame, text="Join Discord", command=lambda: webbrowser.open("https://discord.gg/HzhCPxeCKY")).grid(row=0, column=0, padx=2, pady=2, sticky="ew")
        ttk.Button(help_frame, text="Visit Website", command=lambda: webbrowser.open("https://hooklinesinker.lol")).grid(row=0, column=1, padx=2, pady=2, sticky="ew")

        # create right panel for installed mods
        installed_frame = ttk.LabelFrame(mod_manager_frame, text="Installed Mods")
        installed_frame.grid(row=0, column=2, padx=5, pady=5, sticky="nsew")

        # create filter frame for installed mods with better organization
        filter_frame = ttk.LabelFrame(installed_frame, text="Filter Options")
        filter_frame.grid(row=0, column=0, sticky="ew", padx=2, pady=2)

        # create search frame (broken atm - will fix in 1.2.2)
        # search_frame = ttk.Frame(filter_frame)
        # search_frame.pack(fill="x", padx=5, pady=2)

        # ttk.Label(search_frame, text="Search:").pack(side="left", padx=5)
        # self.installed_search_var = tk.StringVar()
        # self.installed_search_var.trace('w', lambda name, index, mode: self.filter_installed_mods())
        # search_entry = ttk.Entry(search_frame, textvariable=self.installed_search_var)
        # search_entry.pack(side="left", fill="x", expand=True, padx=5)

        # create category frame
        category_frame = ttk.Frame(filter_frame)
        category_frame.pack(fill="x", padx=5, pady=2)

        ttk.Label(category_frame, text="Status:").pack(side="left", padx=5)
        self.installed_category = ttk.Combobox(category_frame, values=["All", "Enabled", "Disabled"], state="readonly")
        self.installed_category.pack(side="left", fill="x", expand=True, padx=5)
        self.installed_category.set("All")
        self.installed_category.bind('<<ComboboxSelected>>', self.filter_installed_mods)

        self.hide_third_party = tk.BooleanVar(value=False)
        ttk.Checkbutton(filter_frame, text="Hide 3rd Party", variable=self.hide_third_party, command=self.filter_installed_mods).pack(fill="x", padx=5, pady=2)

        # create listbox for installed mods with scrollbar
        self.installed_listbox = tk.Listbox(installed_frame, width=30, height=15, selectmode=tk.EXTENDED)
        installed_scrollbar = ttk.Scrollbar(installed_frame, orient="vertical", command=self.installed_listbox.yview)
        self.installed_listbox.configure(yscrollcommand=installed_scrollbar.set)
        
        self.installed_listbox.grid(row=1, column=0, pady=2, padx=2, sticky="nsew")
        installed_scrollbar.grid(row=1, column=1, pady=2, sticky="ns")
        
        self.installed_listbox.bind('<<ListboxSelect>>', self.update_mod_details)
        self.installed_listbox.bind('<Button-3>', self.show_context_menu)

        installed_frame.grid_columnconfigure(0, weight=1)
        installed_frame.grid_rowconfigure(1, weight=1)

        # create bottom panel for mod details
        self.mod_details_frame = ttk.LabelFrame(mod_manager_frame, text="Mod Details")
        self.mod_details_frame.grid(row=1, column=0, columnspan=3, padx=5, pady=5, sticky="nsew")

        self.mod_image = ttk.Label(self.mod_details_frame)
        self.mod_image.grid(row=0, column=0, padx=5, pady=5, sticky="nw")

        self.mod_details = tk.Text(self.mod_details_frame, wrap=tk.WORD, height=12, state='disabled')
        self.mod_details.grid(row=0, column=1, pady=2, padx=2, sticky="nsew")

        self.mod_details_frame.grid_columnconfigure(1, weight=1)
        self.mod_details_frame.grid_rowconfigure(0, weight=1)

    def view_deprecated_mods_list(self):
        messagebox.showinfo("Deprecated Mods List", "This will open a new tab with the deprecated mods list. Note that these mods may be outdated, broken, or no longer work. If you download one, you'll need to import it via the 'Import ZIP' option.")
        webbrowser.open("https://notnite.github.io/webfishing-mods")

    def on_available_listbox_select(self, event):
        self.update_mod_details(event)
        self.check_selection_limit(event)

    def check_selection_limit(self, event):
        listbox = event.widget
        if listbox != self.available_listbox:
            return
            
        selected = listbox.curselection()
        
        # ignore category headers
        actual_mods = [i for i in selected if not listbox.get(i).startswith('--')]
        
        if len(actual_mods) > 3:
            # keep only the first 3 selections
            listbox.selection_clear(0, tk.END)
            for i in actual_mods[:3]:
                listbox.selection_set(i)
            messagebox.showinfo("Selection Limit", "You can only select up to 3 mods for installation at once. This is to fix an issue with severe lag when installing many mods at once.")

    def set_status_safe(self, message):
        if threading.current_thread() is threading.main_thread():
            self.set_status(message)
        else:
            self.root.after(0, self.set_status, message)

    def _format_timestamp(self, timestamp):
        try:
            # convert iso format to datetime
            updated_dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
            now = datetime.now(timezone.utc)
            diff = now - updated_dt
            
            if diff.days > 365:
                years = diff.days // 365
                return f"{years} year{'s' if years != 1 else ''} ago"
            elif diff.days > 30:
                months = diff.days // 30
                return f"{months} month{'s' if months != 1 else ''} ago"
            elif diff.days > 0:
                return f"{diff.days} day{'s' if diff.days != 1 else ''} ago"
            elif diff.seconds > 3600:
                hours = diff.seconds // 3600
                return f"{hours} hour{'s' if hours != 1 else ''} ago"
            else:
                minutes = (diff.seconds % 3600) // 60
                return f"{minutes} minute{'s' if minutes != 1 else ''} ago"
        except Exception:
            return None

    def _show_category_details(self, category_name):
        # remove the category prefix if present
        category_name = category_name.replace('-- ', '').replace(' --', '')
        
        self.mod_details.config(state='normal')
        self.mod_details.delete(1.0, tk.END)
        
        # title section
        self.mod_details.insert(tk.END, f"{category_name} Category\n\n", "header")
        self.mod_details.tag_config("header", font=("TkDefaultFont", 10, "bold"))
        
        # count mods in this category
        mod_count = sum(1 for mod in self.available_mods if category_name in mod.get('categories', []))
        self.mod_details.insert(tk.END, f"Contains {mod_count} mod{'s' if mod_count != 1 else ''}\n\n")
        
        # list mods in category
        if mod_count > 0:
            self.mod_details.insert(tk.END, "Mods in this category:\n", "subheader")
            self.mod_details.tag_config("subheader", font=("TkDefaultFont", 9, "bold"))
            for mod in sorted(self.available_mods, key=lambda x: x['title']):
                if category_name in mod.get('categories', []):
                    self.mod_details.insert(tk.END, f"• {mod['title']} v{mod.get('version', '?')} by {mod.get('author', 'Unknown')}\n")
        
        self.mod_details.config(state='disabled')
        
    def filter_available_mods(self, event=None):
        search_text = self.search_var.get().lower()
        selected_category = self.available_category.get()
        self.available_listbox.delete(0, tk.END)
        
        filtered_mods = []
        for mod in self.available_mods:
            # Check if mod matches search criteria
            if search_text and not (
                search_text in mod['title'].lower() or 
                search_text in mod.get('author', '').lower() or 
                search_text in mod.get('description', '').lower()
            ):
                continue
                
            # Check if mod matches category filter
            if selected_category != "All" and selected_category not in mod.get('categories', []):
                continue
                
            filtered_mods.append(mod)

        # Display filtered mods in a flat sorted list with converted display names
        for mod in sorted(filtered_mods, key=lambda x: x['title']):
            display_title = self.get_display_name(mod['title'])
            self.available_listbox.insert(tk.END, display_title)

    def check_for_duplicate_mods(self):
        mod_ids = {}
        mod_titles = {}
        duplicates = []
        processed_duplicates = set()

        # check normal mods
        for mod_folder in os.listdir(self.mods_dir):
            mod_info_path = os.path.join(self.mods_dir, mod_folder, 'mod_info.json')
            if os.path.exists(mod_info_path):
                with open(mod_info_path, 'r') as f:
                    mod_info = json.load(f)
                    mod_id = mod_info.get('id')
                    mod_title = mod_info.get('title')
                    mod_version = mod_info.get('version', 'Unknown')
                    
                    # check for duplicate ids
                    if mod_id:
                        if mod_id in mod_ids and mod_id not in processed_duplicates:
                            duplicates.append((mod_ids[mod_id], mod_info_path, mod_id, mod_title, mod_version))
                            processed_duplicates.add(mod_id)
                        else:
                            mod_ids[mod_id] = mod_info_path
                    
                    # check for duplicate titles
                    if mod_title:
                        if mod_title in mod_titles and mod_title not in processed_duplicates:
                            duplicates.append((mod_titles[mod_title], mod_info_path, mod_title, mod_id, mod_version))
                            processed_duplicates.add(mod_title)
                        else:
                            mod_titles[mod_title] = mod_info_path

        # check third-party mods
        third_party_mods_dir = os.path.join(self.mods_dir, "3rd_party")
        if os.path.exists(third_party_mods_dir):
            for mod_folder in os.listdir(third_party_mods_dir):
                mod_info_path = os.path.join(third_party_mods_dir, mod_folder, 'mod_info.json')
                if os.path.exists(mod_info_path):
                    with open(mod_info_path, 'r') as f:
                        mod_info = json.load(f)
                        mod_id = mod_info.get('id')
                        mod_title = mod_info.get('title')
                        mod_version = mod_info.get('version', 'Unknown')
                        
                        # check for duplicate ids
                        if mod_id:
                            if mod_id in mod_ids and mod_id not in processed_duplicates:
                                duplicates.append((mod_ids[mod_id], mod_info_path, mod_id, mod_title, mod_version))
                                processed_duplicates.add(mod_id)
                            else:
                                mod_ids[mod_id] = mod_info_path
                        
                        # check for duplicate titles
                        if mod_title:
                            if mod_title in mod_titles and mod_title not in processed_duplicates:
                                duplicates.append((mod_titles[mod_title], mod_info_path, mod_title, mod_id, mod_version))
                                processed_duplicates.add(mod_title)
                            else:
                                mod_titles[mod_title] = mod_info_path

        # handle duplicates
        for original, duplicate, duplicate_identifier, duplicate_title, duplicate_version in duplicates:
            original_version = 'Unknown'
            with open(original, 'r') as f:
                original_info = json.load(f)
                original_version = original_info.get('version', 'Unknown')
            if messagebox.askyesno("Duplicate Mod Found", f"Duplicate mod found: {duplicate_title} {duplicate_version} ({duplicate_identifier}) and {duplicate_title} {original_version} ({duplicate_identifier}), would you like to delete the oldest version to fix this confliction?"):
                try:
                    duplicate_folder = os.path.dirname(duplicate)
                    shutil.rmtree(duplicate_folder)
                    self.set_status(f"Removed duplicate mod: {os.path.basename(duplicate_folder)}")
                except FileNotFoundError:
                    messagebox.showerror("Error", f"The file {duplicate_folder} was already deleted.")
                except Exception as e:
                    messagebox.showerror("Error", f"Failed to delete duplicate mod: {str(e)}")
        self.refresh_mod_lists()

    def filter_installed_mods(self, event=None):
        selected_filter = self.installed_category.get()
        # search_text = self.installed_search_var.get().lower()
        hide_third_party = self.hide_third_party.get()
        self.installed_listbox.delete(0, tk.END)

        for mod in self.installed_mods:
            status = "✅" if mod.get('enabled', True) else "❌"
            
            # Skip if hiding 3rd party and mod is 3rd party
            if hide_third_party and mod.get('third_party', False):
                continue
            
            # # check if mod matches search criteria
            # if search_text and not (
            #     search_text in mod['title'].lower() or 
            #     search_text in mod.get('author', '').lower() or
            #     search_text in mod.get('description', '').lower()
            # ):
            #     continue
                
            # check if mod matches status filter
            if (
                selected_filter == "All" or
                (selected_filter == "Enabled" and mod.get('enabled', True)) or
                (selected_filter == "Disabled" and not mod.get('enabled', True))
            ):
                mod_title = f"{status} {mod['title']}"
                self.installed_listbox.insert(tk.END, mod_title)


    def toggle_game(self):
        if not self.check_setup():
            messagebox.showinfo("Setup Required", "Please follow all the steps for installation in the HLS Setup tab.")
            self.notebook.select(3)  # switch to hls setup tab
            return

        try:
            # launch the game through Steam
            steam_url = "steam://rungameid/3146520"
            webbrowser.open(steam_url)
            self.set_status("Game launched through Steam")
        except Exception as e:
            error_message = f"Failed to launch the game: {str(e)}"
            messagebox.showerror("Error", error_message)
            self.set_status(error_message)

    def create_game_manager_tab(self):
        # create the game manager tab for managing save files
        game_manager_frame = ttk.Frame(self.notebook)
        self.notebook.add(game_manager_frame, text="Save Manager")

        game_manager_frame.grid_columnconfigure(0, weight=1)
        game_manager_frame.grid_rowconfigure(5, weight=1)  # increased to accommodate the subtitle

        # create title and subtitle
        title_label = ttk.Label(game_manager_frame, text="Save Manager", font=("Helvetica", 16, "bold"))
        title_label.grid(row=0, column=0, pady=(20, 5), padx=20, sticky="w")

        subtitle_label = ttk.Label(game_manager_frame, text="Backup and restore your game progress", font=("Helvetica", 10, "italic"))
        subtitle_label.grid(row=1, column=0, pady=(0, 10), padx=20, sticky="w")

        # display save file location
        save_path = os.path.join(os.getenv('APPDATA'), 'Godot', 'app_userdata', 'webfishing_2_newver', 'webfishing_migrated_data.save')
        save_label = ttk.Label(game_manager_frame, text="Save file location:")
        save_label.grid(row=2, column=0, pady=(0, 5), padx=20, sticky="w")
        
        save_path_entry = ttk.Entry(game_manager_frame, width=70)
        save_path_entry.insert(0, save_path)
        save_path_entry.config(state='readonly')
        save_path_entry.grid(row=3, column=0, pady=(0, 10), padx=20, sticky="w")

        # create backup frame
        backup_frame = ttk.LabelFrame(game_manager_frame, text="Backup Save")
        backup_frame.grid(row=4, column=0, pady=10, padx=20, sticky="ew")
        backup_frame.grid_columnconfigure(1, weight=1)

        ttk.Label(backup_frame, text="Backup Name:").grid(row=0, column=0, pady=5, padx=5, sticky="w")
        self.backup_name_entry = ttk.Entry(backup_frame)
        self.backup_name_entry.grid(row=0, column=1, pady=5, padx=5, sticky="ew")
        ttk.Button(backup_frame, text="Create Backup", command=self.create_backup).grid(row=0, column=2, pady=5, padx=5)

        # create restore frame
        restore_frame = ttk.LabelFrame(game_manager_frame, text="Manage Saves")
        restore_frame.grid(row=5, column=0, pady=10, padx=20, sticky="nsew")
        restore_frame.grid_columnconfigure(0, weight=1)
        restore_frame.grid_rowconfigure(0, weight=1)

        # create treeview for backups
        self.backup_tree = ttk.Treeview(restore_frame, columns=('Name', 'Timestamp'), show='headings', height=10)
        self.backup_tree.heading('Name', text='Name')
        self.backup_tree.heading('Timestamp', text='Timestamp')
        self.backup_tree.column('Name', width=200)
        self.backup_tree.column('Timestamp', width=200)
        self.backup_tree.grid(row=0, column=0, pady=5, padx=5, sticky="nsew")
        
        # add scrollbar to treeview
        scrollbar = ttk.Scrollbar(restore_frame, orient="vertical", command=self.backup_tree.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.backup_tree.configure(yscrollcommand=scrollbar.set)
        
        # create buttons frame
        buttons_frame = ttk.Frame(restore_frame)
        buttons_frame.grid(row=1, column=0, columnspan=2, pady=5, padx=5, sticky="ew")
        buttons_frame.grid_columnconfigure((0, 1, 2), weight=1)

        ttk.Button(buttons_frame, text="Restore Selected", command=self.restore_backup).grid(row=0, column=0, padx=5, sticky="ew")
        ttk.Button(buttons_frame, text="Delete Selected", command=self.delete_backup).grid(row=0, column=1, padx=5, sticky="ew")
        ttk.Button(buttons_frame, text="Refresh List", command=self.refresh_backup_list).grid(row=0, column=2, padx=5, sticky="ew")

        # refresh backup list
        self.refresh_backup_list()

    def refresh_backup_list(self):
        # refresh the list of backups in the treeview
        for i in self.backup_tree.get_children():
            self.backup_tree.delete(i)
        
        backup_dir = os.path.join(self.app_data_dir, 'save_backups')
        if os.path.exists(backup_dir):
            backups = sorted([f for f in os.listdir(backup_dir) if f.endswith('.save')], reverse=True)
            for backup in backups:
                name_parts = backup.rsplit('_', 1)
                if len(name_parts) == 2:
                    name = name_parts[0].replace('_', ' ')
                    try:
                        timestamp = float(name_parts[1].replace('.save', ''))
                        formatted_time = datetime.fromtimestamp(timestamp).strftime("%I:%M%p %d/%m/%Y")
                        self.backup_tree.insert('', 'end', values=(name, formatted_time))
                    except ValueError:
                        self.backup_tree.insert('', 'end', values=(backup, 'Unknown'))
                else:
                    self.backup_tree.insert('', 'end', values=(backup, 'Unknown'))
        self.set_status("Backup list refreshed")

    def create_backup(self):
        # create a backup of the current save file
        backup_name = self.backup_name_entry.get().strip()
        if not backup_name:
            messagebox.showerror("Error", "Please enter a backup name.")
            self.set_status("Backup creation failed: No name provided")
            return

        # sanitize the backup name
        invalid_chars = r'<>:"/\|?*'
        sanitized_name = ''.join(c for c in backup_name if c not in invalid_chars)
        sanitized_name = sanitized_name[:255]  # limit to 255 characters

        if not sanitized_name:
            messagebox.showerror("Error", "The backup name contains only invalid characters. Please use a different name.")
            self.set_status("Backup creation failed: Invalid name")
            return

        timestamp = int(time.time())
        backup_filename = f"{sanitized_name.replace(' ', '_')}_{timestamp}.save"

        save_path = os.path.join(os.getenv('APPDATA'), 'Godot', 'app_userdata', 'webfishing_2_newver', 'webfishing_migrated_data.save')
        backup_dir = os.path.join(self.app_data_dir, 'save_backups')
        os.makedirs(backup_dir, exist_ok=True)

        backup_path = os.path.join(backup_dir, backup_filename)

        try:
            shutil.copy2(save_path, backup_path)
            messagebox.showinfo("Success", f"Backup created: {sanitized_name}")
            self.set_status(f"Backup created: {sanitized_name}")
            self.refresh_backup_list()
        except Exception as e:
            error_message = f"Failed to create backup: {str(e)}"
            messagebox.showerror("Error", error_message)
            self.set_status(error_message)

    def check_migration_needed(self):
        """Check if migration from old format is needed and handle it"""
        # skip if already migrated or fresh install
        if self.settings.get('thunderstore_migrated', False):
            return
            
        # check if old mods exist
        gdweave_path = os.path.join(self.settings.get('game_path', ''), 'GDWeave', 'Mods')
        has_old_mods = os.path.exists(gdweave_path) and os.listdir(gdweave_path)
        
        if has_old_mods:
            message = (
                "We've detected you've previously used Hook, Line, & Sinker before the Thunderstore update. "
                "To use Hook, Line, & Sinker with the new version, we must completely clear your existing mods to work with the new system.\n\n"
                "Don't worry - all your saves, backups, settings, and mod configurations will transfer over, only the mods need to be cleared.\n\n" 
                "Press Yes to clear all mods and continue, or No to exit and backup your mods first.\n\n"
                "Warning: This will delete all currently installed mods!"
            )
            if messagebox.askyesno("Migration Required", message):
                try:
                    # clear gdweave mods
                    gdweave_mods_dir = os.path.join(self.settings['game_path'], 'GDWeave', 'Mods')
                    if os.path.exists(gdweave_mods_dir):
                        shutil.rmtree(gdweave_mods_dir)
                        os.makedirs(gdweave_mods_dir)
                    
                    # clear hls mods
                    if os.path.exists(self.mods_dir):
                        shutil.rmtree(self.mods_dir)
                        os.makedirs(self.mods_dir)
                    
                    # update settings
                    self.settings['thunderstore_migrated'] = True
                    self.save_settings()
                    
                    self.set_status("Migration complete - mods cleared for Thunderstore update")
                    messagebox.showinfo("Migration Complete", 
                        "Migration completed successfully. You can now install mods from Thunderstore.")
                    
                except Exception as e:
                    error_msg = f"Failed to migrate: {str(e)}"
                    logging.error(error_msg)
                    self.set_status(error_msg)
                    messagebox.showerror("Migration Failed", 
                        "Failed to complete migration. Please try again or contact support.")
                    sys.exit(1)
            else:
                messagebox.showinfo("Application Closing",
                    "Please backup your mods and restart the application when ready to migrate.")
                sys.exit(0)

    def restore_backup(self):
        # restore a selected backup
        selected = self.backup_tree.selection()
        if not selected:
            messagebox.showerror("Error", "Please select a backup to restore.")
            self.set_status("Backup restoration failed: No backup selected")
            return

        item = self.backup_tree.item(selected[0])
        backup_name = item['values'][0]
        
        backup_dir = os.path.join(self.app_data_dir, 'save_backups')
        matching_backups = [f for f in os.listdir(backup_dir) if f.startswith(backup_name.replace(' ', '_')) and f.endswith('.save')]
        
        if not matching_backups:
            error_message = f"Backup file for '{backup_name}' not found."
            messagebox.showerror("Error", error_message)
            self.set_status(error_message)
            return
        
        backup_filename = matching_backups[0]  # use the first matching backup if multiple exist
        backup_path = os.path.join(backup_dir, backup_filename)

        save_path = os.path.join(os.getenv('APPDATA'), 'Godot', 'app_userdata', 'webfishing_2_newver', 'webfishing_migrated_data.save')

        try:
            # restore the selected backup
            shutil.copy2(backup_path, save_path)
            messagebox.showinfo("Success", f"Backup restored: {backup_name}")
            self.set_status(f"Backup restored: {backup_name}")
            self.refresh_backup_list()
        except Exception as e:
            error_message = f"Failed to restore backup: {str(e)}"
            messagebox.showerror("Error", error_message)
            self.set_status(error_message)

    def delete_backup(self):
        selected = self.backup_tree.selection()
        if not selected:
            messagebox.showerror("Error", "Please select a backup to delete.")
            self.set_status("Backup deletion failed: No backup selected")
            return

        item = self.backup_tree.item(selected[0])
        backup_name = item['values'][0]
        
        if messagebox.askyesno("Confirm Delete", f"Are you sure you want to delete the backup '{backup_name}'?"):
            backup_dir = os.path.join(self.app_data_dir, 'save_backups')
            matching_backups = [f for f in os.listdir(backup_dir) if f.startswith(backup_name.replace(' ', '_')) and f.endswith('.save')]
            
            if not matching_backups:
                error_message = f"Backup file for '{backup_name}' not found."
                messagebox.showerror("Error", error_message)
                self.set_status(error_message)
                return
            
            backup_filename = matching_backups[0]
            backup_path = os.path.join(backup_dir, backup_filename)
            
            try:
                os.remove(backup_path)
                messagebox.showinfo("Success", f"Backup deleted: {backup_name}")
                self.set_status(f"Backup deleted: {backup_name}")
                self.refresh_backup_list()
            except Exception as e:
                error_message = f"Failed to delete backup: {str(e)}"
                messagebox.showerror("Error", error_message)
                self.set_status(error_message)

    # creates the main setup tab for hook line & sinker
    def create_hls_setup_tab(self):
        setup_frame = ttk.Frame(self.notebook)
        self.notebook.add(setup_frame, text="HLS Setup")

        setup_frame.grid_columnconfigure(0, weight=1)
        setup_frame.grid_rowconfigure(8, weight=1)  # increased to accommodate new button

        # title
        title_label = ttk.Label(setup_frame, text="Game Setup Guide", font=("Helvetica", 16, "bold"))
        title_label.grid(row=0, column=0, pady=(20, 5), padx=20, sticky="w")

        # new label for instructions
        instruction_label = ttk.Label(setup_frame, text="You must complete all steps below to use Hook, Line, & Sinker", font=("Helvetica", 10, "italic"))
        instruction_label.grid(row=1, column=0, pady=(0, 10), padx=20, sticky="w")

        # step 1: set game path
        step1_frame = ttk.LabelFrame(setup_frame, text="Step 1: Set Game Installation Path")
        step1_frame.grid(row=2, column=0, pady=10, padx=20, sticky="ew")
        step1_frame.grid_columnconfigure(1, weight=1)

        ttk.Label(step1_frame, text="Path:").grid(row=0, column=0, pady=5, padx=5, sticky="w")
        self.game_path_entry = ttk.Entry(step1_frame, width=40)
        self.game_path_entry.grid(row=0, column=1, pady=5, padx=5, sticky="ew")
        self.game_path_entry.insert(0, self.settings.get('game_path', ''))

        ttk.Button(step1_frame, text="Browse", command=self.browse_game_directory).grid(row=0, column=2, pady=5, padx=5)
        ttk.Button(step1_frame, text="Save Path", command=self.save_game_path).grid(row=0, column=3, pady=5, padx=5)

        self.step1_status = ttk.Label(step1_frame, text="Unverified", foreground="red", font=("Helvetica", 10, "bold"))
        self.step1_status.grid(row=1, column=0, columnspan=4, pady=5, padx=5, sticky="w")

        # step 2: verify installation
        step2_frame = ttk.LabelFrame(setup_frame, text="Step 2: Verify Game Installation")
        step2_frame.grid(row=3, column=0, pady=10, padx=20, sticky="ew")
        step2_frame.grid_columnconfigure(1, weight=1)

        ttk.Button(step2_frame, text="Verify Installation", command=self.verify_installation).grid(row=0, column=0, pady=5, padx=5)
        ttk.Label(step2_frame, text="Checks if the game files are present in the specified path.").grid(row=0, column=1, pady=5, padx=5, sticky="w")

        self.step2_status = ttk.Label(step2_frame, text="Unverified", foreground="red", font=("Helvetica", 10, "bold"))
        self.step2_status.grid(row=1, column=0, columnspan=2, pady=5, padx=5, sticky="w")

        # step 3: install net
        step3_frame = ttk.LabelFrame(setup_frame, text="Step 3: Install .NET")
        step3_frame.grid(row=4, column=0, pady=10, padx=20, sticky="ew")
        step3_frame.grid_columnconfigure(0, weight=1)

        ttk.Label(step3_frame, text="Visit the .NET download page and install the .NET 8.0 SDK:").grid(row=0, column=0, pady=5, padx=5, sticky="w")
        
        dotnet_link = ttk.Label(step3_frame, text=".NET Download Page", foreground="blue", cursor="hand2")
        dotnet_link.grid(row=1, column=0, pady=5, padx=5, sticky="w")
        dotnet_link.bind("<Button-1>", lambda e: webbrowser.open("https://dotnet.microsoft.com/en-us/download"))

        ttk.Label(step3_frame, text="Click the 'Download .NET SDK x64' or 'Download .NET SDK x86' button as appropriate for your system.").grid(row=2, column=0, pady=5, padx=5, sticky="w")
        ttk.Label(step3_frame, text="Note: We cannot automatically verify this step. Please ensure you've completed it before proceeding.").grid(row=3, column=0, pady=5, padx=5, sticky="w")

        # step 4: install/update gdweave
        step4_frame = ttk.LabelFrame(setup_frame, text="Step 4: Install/Update GDWeave")
        step4_frame.grid(row=5, column=0, pady=10, padx=20, sticky="ew")
        step4_frame.grid_columnconfigure(1, weight=1)

        self.gdweave_button = ttk.Button(step4_frame, text="Install GDWeave", command=self.install_gdweave)
        self.gdweave_button.grid(row=0, column=0, pady=5, padx=5)
        self.gdweave_label = ttk.Label(step4_frame, text="Installs or updates GDWeave mod loader. Your mods should transfer over, backup just in case.")
        self.gdweave_label.grid(row=0, column=1, pady=5, padx=5, sticky="w")

        self.step4_status = ttk.Label(step4_frame, text="Uninstalled", foreground="red", font=("Helvetica", 10, "bold"))
        self.step4_status.grid(row=1, column=0, columnspan=2, pady=5, padx=5, sticky="w")

        # setup status
        self.setup_status = ttk.Label(setup_frame, text="", font=("Helvetica", 12))
        self.setup_status.grid(row=6, column=0, pady=(20, 10), padx=20, sticky="w")
        self.update_setup_status()
    # creates the settings tab for hook line & sinker
    def create_settings_tab(self):
        settings_frame = ttk.Frame(self.notebook)
        self.notebook.add(settings_frame, text="Settings")

        settings_frame.grid_columnconfigure(0, weight=1)
        settings_frame.grid_rowconfigure(7, weight=1)

        # title
        title_label = ttk.Label(settings_frame, text="Application Settings", font=("Helvetica", 16, "bold"))
        title_label.grid(row=0, column=0, pady=(20, 5), padx=20, sticky="w")

        # subtitle
        subtitle_label = ttk.Label(settings_frame, text="Customize your Hook, Line, & Sinker experience", font=("Helvetica", 10, "italic"))
        subtitle_label.grid(row=1, column=0, pady=(0, 10), padx=20, sticky="w")

        # general settings
        general_frame = ttk.LabelFrame(settings_frame, text="General Settings")
        general_frame.grid(row=2, column=0, pady=10, padx=20, sticky="ew")
        general_frame.grid_columnconfigure(1, weight=1)

        self.auto_update = tk.BooleanVar(value=self.settings.get('auto_update', True))
        ttk.Checkbutton(general_frame, text="Auto-update mods", variable=self.auto_update, command=self.save_settings).grid(row=0, column=0, columnspan=2, pady=5, padx=5, sticky="w")
        self.windowed_mode = tk.BooleanVar(value=self.settings.get('windowed_mode', False))
        ttk.Checkbutton(general_frame, text="Launch in windowed mode", 
                variable=self.windowed_mode, 
                command=self.save_windowed_mode).grid(row=1, column=0, columnspan=2, pady=5, padx=5, sticky="w")

        update_frame = ttk.Frame(general_frame)
        update_frame.grid(row=2, column=0, columnspan=2, pady=5, padx=5, sticky="w")
        update_frame.grid_columnconfigure(1, weight=1)

        ttk.Button(update_frame, text="Check for Updates", command=self.check_for_updates).grid(row=0, column=0, pady=2, padx=(0, 5), sticky="w")
        ttk.Label(update_frame, text="Check for application and mod updates").grid(row=0, column=1, pady=2, padx=5, sticky="w")

        # hook line & sinker information
        info_frame = ttk.LabelFrame(settings_frame, text="Hook, Line, & Sinker Information")
        info_frame.grid(row=3, column=0, pady=10, padx=20, sticky="ew")
        info_frame.grid_columnconfigure(1, weight=1)

        # load current version
        current_version = get_version()

        self.current_version_label = ttk.Label(info_frame, text=f"Current Version: {current_version}")
        self.current_version_label.grid(row=0, column=0, columnspan=2, pady=5, padx=5, sticky="w")

        self.latest_version_label = ttk.Label(info_frame, text="Latest Version: Checking...")
        self.latest_version_label.grid(row=1, column=0, columnspan=2, pady=5, padx=5, sticky="w")

        ttk.Button(info_frame, text="View Changelog", command=self.show_changelog).grid(row=2, column=0, pady=5, padx=5, sticky="w")
        ttk.Label(info_frame, text="View application changelog").grid(row=2, column=1, pady=5, padx=5, sticky="w")

        ttk.Button(info_frame, text="View Credits", command=self.show_credits).grid(row=3, column=0, pady=5, padx=5, sticky="w")
        ttk.Label(info_frame, text="View application credits").grid(row=3, column=1, pady=5, padx=5, sticky="w")

        # troubleshooting options
        troubleshoot_frame = ttk.LabelFrame(settings_frame, text="Troubleshooting")
        troubleshoot_frame.grid(row=5, column=0, pady=10, padx=20, sticky="ew")
        troubleshoot_frame.grid_columnconfigure((0, 1, 2), weight=1)

        # first row - most important actions
        self.toggle_gdweave_button = ttk.Button(troubleshoot_frame, text="Toggle GDWeave", command=self.toggle_gdweave)
        self.toggle_gdweave_button.grid(row=0, column=0, pady=5, padx=5, sticky="ew")
        ttk.Button(troubleshoot_frame, text="Clear GDWeave Mods", command=self.clear_gdweave_mods).grid(row=0, column=1, pady=5, padx=5, sticky="ew")
        ttk.Button(troubleshoot_frame, text="Clear HLS Mods", command=self.clear_hls_mods).grid(row=0, column=2, pady=5, padx=5, sticky="ew")

        # second row - log access
        ttk.Button(troubleshoot_frame, text="Open GDWeave Log", command=self.open_gdweave_log).grid(row=1, column=0, pady=5, padx=5, sticky="ew")
        ttk.Button(troubleshoot_frame, text="Open HLS Log", command=self.open_latest_log).grid(row=1, column=1, pady=5, padx=5, sticky="ew")
        ttk.Button(troubleshoot_frame, text="Open Full HLS Log", command=self.open_full_log).grid(row=1, column=2, pady=5, padx=5, sticky="ew")

        # third row - folders and additional options
        ttk.Button(troubleshoot_frame, text="Open HLS Folder", command=self.open_hls_folder).grid(row=2, column=0, pady=5, padx=5, sticky="ew")
        ttk.Button(troubleshoot_frame, text="Open GDWeave Folder", command=self.open_gdweave_folder).grid(row=2, column=1, pady=5, padx=5, sticky="ew")
        ttk.Button(troubleshoot_frame, text="Clear Temp Folder", command=self.delete_temp_files).grid(row=2, column=2, pady=5, padx=5, sticky="ew")

        # settings status
        self.settings_status = ttk.Label(settings_frame, text="", font=("Helvetica", 12))
        self.settings_status.grid(row=6, column=0, pady=(10, 20), padx=20, sticky="w")

        # start a thread to check the latest version
        threading.Thread(target=self.update_latest_version_label, daemon=True).start()
        self.root.after(100, self.process_gui_queue)

    def save_windowed_mode(self):
        self.settings['windowed_mode'] = self.windowed_mode.get()
        self.save_settings()

    def show_credits(self):
        credits_text = """Credits:

Development:
• Pyoid - Creator of Hook, Line, & Sinker
• NotNite - Creator of GDWeave

Discord Staff:
• Daniela - Discord Administrator
• Sulayre - Discord Administrator

HLS Supporters:
• betrel, box, david, eZbake, fern, Goobercide, ivy, Maxx, mika, Moro the Webfisher, Munch, Nipi, Nokuuu, PMPKIN, Pongorma, sheebs, shiro, Snowy, sunday, ThatFirey, Vival, Wes

Special Thanks:
• All mod creators for their contributions
• You for using Hook, Line, & Sinker!"""
        messagebox.showinfo("Credits", credits_text)

    def show_changelog(self):
        try:
            if getattr(sys, 'frozen', False):
                # running as compiled executable
                bundle_dir = sys._MEIPASS
            else:
                # running in a normal python environment
                bundle_dir = os.path.dirname(os.path.abspath(__file__))
            
            version_file = os.path.join(bundle_dir, 'version.json')
            
            with open(version_file, 'r') as f:
                version_data = json.load(f)
            
            changelog = version_data.get('changelog', [])
            
            changelog_text = "Changelog:\n\n"

            for item in changelog:
                changelog_text += f"• {item}\n\n"
            
            messagebox.showinfo("Changelog", changelog_text)

        except Exception as e:
            logging.error(f"Error showing changelog: {e}")

            messagebox.showerror("Error", f"Failed to load changelog: {e}")
    # opens the help website in the default browser
    def open_help_website(self):
        webbrowser.open("https://hooklinesinker.lol/help")

    # copies existing gdweave mods to the hls mods directory
    def copy_existing_gdweave_mods(self):
        if not self.settings.get('game_path'):
            logging.info("Game path not set, skipping existing mod copy.")
            return

        gdweave_mods_path = os.path.join(self.settings['game_path'], 'GDWeave', 'Mods')
        if not os.path.exists(gdweave_mods_path):
            logging.info("GDWeave Mods folder not found, skipping existing mod copy.")
            return

        third_party_mods_dir = os.path.join(self.mods_dir, "3rd_party")
        os.makedirs(third_party_mods_dir, exist_ok=True)

        # get the list of known mod ids from our managed mods
        known_mod_ids = set()
        for mod_folder in os.listdir(self.mods_dir):
            mod_info_path = os.path.join(self.mods_dir, mod_folder, 'mod_info.json')
            if os.path.exists(mod_info_path):
                with open(mod_info_path, 'r') as f:
                    mod_info = json.load(f)
                    known_mod_ids.add(mod_info.get('id'))

        newly_installed_mods = []

        for mod_folder in os.listdir(gdweave_mods_path):
            src_mod_path = os.path.join(gdweave_mods_path, mod_folder)
            
            if not os.path.isdir(src_mod_path):
                logging.info(f"Skipped: {mod_folder} (not a directory)")
                continue

            manifest_path = os.path.join(src_mod_path, 'manifest.json')
            if not os.path.exists(manifest_path):
                logging.info(f"Skipped: {mod_folder} (no manifest.json found)")
                continue

            try:
                with open(manifest_path, 'r') as f:
                    manifest = json.load(f)
                
                mod_id = manifest.get('Id')
                mod_title = manifest.get('Name', mod_folder)
                mod_author = manifest.get('Author', 'Unknown')
                mod_description = manifest.get('Description', 'No description provided')
                mod_version = manifest.get('Version', 'Unknown')

                # check if this is a known mod
                if mod_id in known_mod_ids:
                    logging.info(f"Skipped known mod: {mod_title} (ID: {mod_id})")
                    continue

                # if we've reached here it's likely a third-party mod
                dst_mod_path = os.path.join(third_party_mods_dir, mod_id)
                if not os.path.exists(dst_mod_path):
                    shutil.copytree(src_mod_path, dst_mod_path)

                    # create mod_info.json
                    mod_info = {
                        'id': mod_id,
                        'title': mod_title,
                        'author': mod_author,
                        'description': mod_description,
                        'enabled': True,
                        'version': mod_version,
                        'third_party': True
                    }
                    with open(os.path.join(dst_mod_path, 'mod_info.json'), 'w') as f:
                        json.dump(mod_info, f, indent=2)

                    logging.info(f"Copied third-party mod: {mod_title} (ID: {mod_id})")
                    newly_installed_mods.append(mod_info)
                else:
                    logging.info(f"Skipped existing third-party mod: {mod_title} (ID: {mod_id})")

            except Exception as e:
                logging.info(f"Error processing mod {mod_folder}: {str(e)}")

        # add newly installed mods to the installed mods list
        self.installed_mods.extend(newly_installed_mods)

        self.refresh_mod_lists()

    # deletes temporary files and folders
    def delete_temp_files(self):
        temp_dir = os.path.join(os.getenv('APPDATA'), 'HookLineSinker', 'temp')
        if os.path.exists(temp_dir):
            try:
                # use os.walk to iterate through all directories and files
                for root, dirs, files in os.walk(temp_dir, topdown=False):
                    for name in files:
                        file_path = os.path.join(root, name)
                        os.chmod(file_path, stat.S_IWRITE)
                        os.remove(file_path)
                    for name in dirs:
                        dir_path = os.path.join(root, name)
                        os.chmod(dir_path, stat.S_IWRITE)
                        os.rmdir(dir_path)
                
                # remove the main directory
                os.chmod(temp_dir, stat.S_IWRITE)
                os.rmdir(temp_dir)
                
                logging.info(f"Successfully deleted temporary directory: {temp_dir}")
                self.set_status("Temporary files and folders deleted successfully.")
            except Exception as e:
                error_message = f"Failed to delete temporary files and folders: {str(e)}"
                logging.error(error_message)
                self.set_status(error_message)
        else:
            logging.info(f"Temporary directory does not exist: {temp_dir}")
            self.set_status("No temporary files or folders to delete.")

    # verifies that net is installed and working correctly    
    def verify_dotnet(self):
        try:
            subprocess.run(["dotnet", "--version"], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            self.set_status(".NET is installed and working correctly.")
        except Exception as e:
            error_message = "Please install the .NET 8.0 SDK. Visit https://dotnet.microsoft.com/download"
            self.set_status(error_message)
            messagebox.showerror("Installation Error", error_message)

    # downloads and runs the net installer
    def download_and_run_dotnet_installer(self):
        self.set_status("Downloading .NET installer...")
        messagebox.showinfo("Downloading .NET", "This will download the .NET 8.0 SDK installer. Please wait 10-20 seconds.")
        
        if not sys.platform.startswith('win'):
            messagebox.showerror("Unsupported OS", "Your operating system is not supported for automatic .NET installation.")
            return
        
        url = "https://download.visualstudio.microsoft.com/download/pr/6224f00f-08da-4e7f-85b1-00d42c2bb3d3/b775de636b91e023574a0bbc291f705a/dotnet-sdk-8.0.403-win-x64.exe"
        
        def download_and_install():
            try:
                # create temp directory in appdata
                temp_dir = os.path.join(os.getenv('APPDATA'), 'HookLineSinker', 'temp')
                os.makedirs(temp_dir, exist_ok=True)
                
                # download the installer
                with requests.get(url, stream=True) as response:
                    response.raise_for_status()
                    total_size = int(response.headers.get('content-length', 0))
                    
                    # create a temporary file to store the installer
                    temp_file_path = os.path.join(temp_dir, 'dotnet_installer.exe')
                    with open(temp_file_path, 'wb') as temp_file:
                        downloaded_size = 0
                        chunk_size = 8192
                        
                        for chunk in response.iter_content(chunk_size=chunk_size):
                            if chunk:
                                temp_file.write(chunk)
                                downloaded_size += len(chunk)
                                self.root.update_idletasks()
                
                self.set_status("Download complete.")

                # run the installer without quiet mode on windows
                subprocess.Popen([temp_file_path, '/norestart'])
                self.set_status("Installer launched. Please follow the installation prompts.")
                messagebox.showinfo("Installation Started", "The .NET installer has been launched. Please follow the installation prompts. After installation, please restart Hook, Line, & Sinker.")

            except Exception as e:
                error_message = f"Failed to download or install .NET: {str(e)}"
                self.set_status(error_message)
                messagebox.showerror("Installation Error", error_message)

            finally:
                # clean up the temporary file
                if 'temp_file_path' in locals():
                    try:
                        os.unlink(temp_file_path)
                    except Exception:
                        pass

        # start the download and installation process in a separate thread
        threading.Thread(target=download_and_install, daemon=True).start()

    # imports a zip mod file
    def import_zip_mod(self):
        zip_path = filedialog.askopenfilename(filetypes=[("ZIP files", "*.zip")])
        if not zip_path:
            logging.info("No ZIP file selected.")
            return

        logging.info(f"Selected ZIP file: {zip_path}")

        # Create temp directories
        temp_dir = os.path.join(self.app_data_dir, 'temp')
        os.makedirs(temp_dir, exist_ok=True)
        import_temp_dir = os.path.join(temp_dir, f"import_{int(time.time())}")
        os.makedirs(import_temp_dir)
        extracted_zip_dir = os.path.join(import_temp_dir, 'extractedzip')
        os.makedirs(extracted_zip_dir)

        try:
            # Extract zip contents
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extractall(extracted_zip_dir)

            manifest_path = self.find_manifest(extracted_zip_dir)
            if not manifest_path:
                error_msg = "manifest.json not found in the ZIP file. This may not be a valid mod package."
                logging.error(error_msg)
                messagebox.showerror("Error", error_msg)
                return

            # Read manifest and check dependencies
            with open(manifest_path, 'r') as f:
                manifest = json.load(f)

            mod_id = manifest.get('Id')
            if not mod_id:
                error_msg = "Id not found in manifest.json. This may not be a valid mod package."
                logging.error(error_msg)
                messagebox.showerror("Error", error_msg)
                return

            if dependencies := manifest.get('Dependencies', []):
                all_dependencies = []
                missing_dependencies = []

                for dep_id in dependencies:
                    if not self.is_mod_installed(dep_id):
                        if dep_mod := self.find_mod_by_id(dep_id):
                            if dep_mod not in all_dependencies:
                                all_dependencies.append(dep_mod)
                        else:
                            missing_dependencies.append(dep_id)

                if all_dependencies or missing_dependencies:
                    message = f"The mod '{manifest.get('Name', mod_id)}' has dependencies:\n\n"

                    if all_dependencies:
                        message += "The following dependencies will be installed:\n"
                        message += "\n".join([f"• {dep['title']}" for dep in all_dependencies])
                        message += "\n"

                    if missing_dependencies:
                        message += "\nThe following dependencies could not be found:\n"
                        message += "\n".join([f"• {dep_id}" for dep in missing_dependencies])
                        message += "\n\nThe mod may not work correctly without these dependencies. Try finding and importing them manually."

                    message += "\n\nWould you like to continue?"

                    if not messagebox.askyesno("Dependencies Required", message):
                        return

                    # Install available dependencies
                    for dep_mod in all_dependencies:
                        self.set_status(f"Installing dependency: {dep_mod['title']}")
                        self.download_and_install_mod(dep_mod)

            # Check if mod already exists
            if self.mod_id_exists(mod_id):
                messagebox.showwarning("Mod Conflict", f"A mod with ID '{mod_id}' already exists. You must uninstall the existing mod before importing a new mod with the same ID.")
                return

            # Continue with mod installation
            mod_dir = os.path.join(self.mods_dir, "3rd_party", mod_id)
            if os.path.exists(mod_dir):
                shutil.rmtree(mod_dir)

            manifest_parent = os.path.dirname(manifest_path)
            if manifest_parent != extracted_zip_dir:
                shutil.move(manifest_parent, mod_dir)
            else:
                shutil.move(extracted_zip_dir, mod_dir)

            # Create mod_info.json
            mod_info = {
                'id': mod_id,
                'title': manifest.get('Metadata', {}).get('Name') or manifest.get('Name', mod_id),
                'author': manifest.get('Metadata', {}).get('Author') or manifest.get('Author', 'Unknown'),
                'description': manifest.get('Metadata', {}).get('Description') or manifest.get('Description', ''),
                'version': manifest.get('Metadata', {}).get('Version') or manifest.get('Version', 'Unknown'),
                'enabled': True,
                'third_party': True
            }

            mod_info_path = os.path.join(mod_dir, 'mod_info.json')
            with open(mod_info_path, 'w') as f:
                json.dump(mod_info, f, indent=2)

            self.set_status(f"3rd party mod '{mod_info['title']}' imported successfully!")
            self.refresh_mod_lists()
            self.copy_mod_to_game(mod_info)

        except Exception as e:
            error_message = f"Failed to import mod: {str(e)}"
            logging.error(error_message)
            logging.error(traceback.format_exc())
            self.set_status(error_message)

    # searches for manifest.json file containing an 'Id' field in a given directory and its subdirectories
    def find_manifest(self, directory):
        for root, dirs, files in os.walk(directory):
            if 'manifest.json' in files:
                manifest_path = os.path.join(root, 'manifest.json')
                try:
                    with open(manifest_path, 'r') as f:
                        manifest_data = json.load(f)
                        if manifest_data.get('Id'):  # only return if Id field exists
                            return manifest_path
                except (json.JSONDecodeError, IOError):
                    continue
        return None
    
    # refreshes all mods by reloading available mods and updating the UI
    def refresh_all_mods(self):
        self.load_available_mods()
        self.refresh_mod_lists()
        self.set_status("All mods refreshed")
        
    # fetches the latest version of GDWeave from GitHub
    # uses a separate thread with a timeout to prevent hanging
    def get_gdweave_version(self):
        def fetch_version():
            try:
                api_url = "https://api.github.com/repos/NotNite/GDWeave/releases/latest"
                response = requests.get(api_url)
                response.raise_for_status()
                data = json.loads(response.text)
                return data['tag_name']
            except Exception as e:
                logging.info(f"Error fetching GDWeave version: {str(e)}")
                return "Unknown"

        result = None
        def run_fetch():
            nonlocal result
            result = fetch_version()

        thread = threading.Thread(target=run_fetch, daemon=True)
        thread.start()
        thread.join(timeout=10)  # wait for up to 10 seconds

        if thread.is_alive():
            logging.info("Timeout occurred while fetching GDWeave version")
            return "0"
        else:
            return result if result is not None else "Unknown"
        
    # installs selected mods from the available mods list
    # handles conflicts with existing mods and third-party mods
    def install_mod(self):
        logging.debug("Starting install_mod()")
        if not self.check_setup():
            logging.debug("Setup check failed")
            return

        selected = self.available_listbox.curselection()
        logging.debug(f"Selected items: {selected}")
        if not selected:
            logging.debug("No mods selected")
            self.set_status("Please select a mod to install")
            return

        # get selected mod titles
        selected_titles = [self.available_listbox.get(index) for index in selected]
        logging.debug(f"Selected titles: {selected_titles}")
        
        # check for protected mods
        protected_mods = ['GDWeave', 'Hook_Line_and_Sinker']
        for title in selected_titles:
            # clean the title and convert display name to backend name
            clean_title = title.replace('✅', '').replace('❌', '').replace('[3rd]', '').strip()
            backend_title = self.get_backend_name(clean_title)
            logging.debug(f"Checking protected status for {backend_title}")
            if backend_title in protected_mods:
                logging.debug(f"{backend_title} is protected, showing error")
                messagebox.showerror(
                    "Protected Mod",
                    f"{clean_title} is a core component and cannot be installed via Thunderstore. " 
                    "It will be managed automatically by Hook, Line, & Sinker."
                )
                return

        all_dependencies = []
        missing_dependencies = []

        try:
            # first check all dependencies
            for index in selected:
                mod_title = self.available_listbox.get(index)
                logging.debug(f"Processing mod: {mod_title}")
                if mod_title.startswith("Category:"):
                    logging.debug("Skipping category header")
                    continue

                # clean the title and convert to backend name for lookup
                clean_title = mod_title.replace('✅', '').replace('❌', '').replace('[3rd]', '').strip()
                backend_title = self.get_backend_name(clean_title)
                logging.debug(f"Cleaned title: {clean_title}, backend title: {backend_title}")
                
                # find the mod using the backend name
                mod = next((m for m in self.available_mods if self.get_backend_name(m['title'].strip()) == backend_title), None)
                if not mod:
                    logging.debug(f"Could not find mod for {backend_title}")
                    continue

                self.set_status_safe(f"Checking dependencies for {mod['title']}...")
                if dependencies := mod.get('dependencies', []):
                    logging.debug(f"Found dependencies for {mod['title']}: {dependencies}")
                    for dep in dependencies:
                        # parse dependency string (format: owner-name-version)
                        parts = dep.split('-')
                        if len(parts) >= 2:
                            thunderstore_id = f"{parts[0]}-{parts[1]}"
                            logging.debug(f"Checking dependency: {thunderstore_id}")
                            # skip gdweave and hls dependencies
                            if thunderstore_id.startswith(('NotNet-GDWeave', 'Pyoid-Hook_Line_and_Sinker')):
                                logging.debug(f"Skipping core dependency: {thunderstore_id}")
                                continue
                            # check if dependency is installed using thunderstore_id
                            if not any(m.get('thunderstore_id') == thunderstore_id for m in self.installed_mods):
                                logging.debug(f"Dependency {thunderstore_id} not installed")
                                if dep_mod := next((m for m in self.available_mods if m.get('thunderstore_id') == thunderstore_id), None):
                                    if dep_mod not in all_dependencies:
                                        logging.debug(f"Adding {thunderstore_id} to dependencies to install")
                                        all_dependencies.append(dep_mod)
                                else:
                                    logging.debug(f"Dependency {thunderstore_id} not found in available mods")
                                    missing_dependencies.append(dep)

            # if there are dependencies, prompt user
            if all_dependencies or missing_dependencies:
                logging.debug(f"Found dependencies to handle - to install: {len(all_dependencies)}, missing: {len(missing_dependencies)}")
                message = ""
                if all_dependencies:
                    message += "The following dependencies will be installed:\n"
                    message += "\n".join([f"• {dep['title']}" for dep in all_dependencies])
                    message += "\n\n"

                if missing_dependencies:
                    message += "The following dependencies could not be found:\n"
                    message += "\n".join([f"• {dep}" for dep in missing_dependencies])
                    message += "\n\nThe mod may not work correctly without these dependencies."

                message += "\n\nWould you like to continue?"

                if not messagebox.askyesno("Dependencies Required", message):
                    logging.debug("User cancelled dependency installation")
                    return

                # install available dependencies first
                for dep_mod in all_dependencies:
                    logging.debug(f"Installing dependency: {dep_mod['title']}")
                    self.set_status_safe(f"Installing dependency: {dep_mod['title']}")
                    self.download_and_install_mod(dep_mod)

            # install selected mods
            for index in selected:
                mod_title = self.available_listbox.get(index)
                logging.debug(f"Installing selected mod: {mod_title}")
                if mod_title.startswith("Category:"):
                    logging.debug("Skipping category header")
                    continue

                clean_title = mod_title.replace('✅', '').replace('❌', '').replace('[3rd]', '').strip()
                backend_title = self.get_backend_name(clean_title)
                mod = next((m for m in self.available_mods if self.get_backend_name(m['title'].strip()) == backend_title), None)
                if not mod:
                    logging.debug(f"Could not find mod for {clean_title}")
                    continue

                self.set_status_safe(f"Installing {mod['title']}")
                logging.debug(f"Downloading and installing {mod['title']}")
                self.download_and_install_mod(mod)

            self.set_status_safe("Installation complete")
            logging.debug("Installation completed successfully")
            self.refresh_mod_lists()

        except Exception as e:
            error_message = f"Installation failed: {str(e)}"
            logging.debug(f"Installation failed with error: {error_message}")
            messagebox.showerror("Error", error_message)
            logging.ERROR(error_message)

    # checks if a mod is installed by its ID
    def is_mod_installed(self, mod_id):
        return any(m['id'] == mod_id for m in self.installed_mods)
    
    def find_mod_by_id(self, mod_id):
        return next((m for m in self.available_mods if m['id'] == mod_id), None)

    def check_mod_dependencies(self, mod):
        missing_deps = []
        for dep in mod.get('dependencies', []):
            # Parse dependency string (format: owner-name-version)
            parts = dep.split('-')
            if len(parts) >= 2:
                thunderstore_id = f"{parts[0]}-{parts[1]}"
                # skip gdweave and hls dependencies
                if thunderstore_id.startswith(('NotNet-GDWeave', 'Pyoid-Hook_Line_and_Sinker')):
                    continue
                # check if dependency is installed using thunderstore_id
                if not any(m.get('thunderstore_id') == thunderstore_id for m in self.installed_mods):
                    missing_deps.append(dep)
        return missing_deps

    # searches for an installed mod by its ID
    # checks both regular and third-party mods
    def find_installed_mod_by_id(self, mod_id):
        # check regular mods
        for mod in self.installed_mods:
            if mod['id'] == mod_id:
                return mod
        
            # check third-party mods
            third_party_dir = os.path.join(self.mods_dir, "3rd_party")
            if os.path.exists(third_party_dir):
                for mod_folder in os.listdir(third_party_dir):
                    mod_info_path = os.path.join(third_party_dir, mod_folder, 'mod_info.json')
                    if os.path.exists(mod_info_path):
                        with open(mod_info_path, 'r') as f:
                            mod_info = json.load(f)
                            if mod_info['id'] == mod_id:
                                return mod_info
            return None
        
        # check third-party mods
        third_party_dir = os.path.join(self.mods_dir, "3rd_party")
        if os.path.exists(third_party_dir):
            for mod_folder in os.listdir(third_party_dir):
                mod_info_path = os.path.join(third_party_dir, mod_folder, 'mod_info.json')
                if os.path.exists(mod_info_path):
                    with open(mod_info_path, 'r') as f:
                        mod_info = json.load(f)
                        if mod_info['id'] == mod_id:
                            return mod_info
        return None

    # installs or updates GDWeave mod loader
    # backs up existing mods and configs before installation
    def install_gdweave(self):
        if not self.settings.get('game_path'):
            self.set_status("Please set the game path first")
            return

        gdweave_url = "https://github.com/NotNite/GDWeave/releases/latest/download/GDWeave.zip"
        game_path = self.settings['game_path']
        gdweave_path = os.path.join(game_path, 'GDWeave')

        try:
            # create a temporary directory for backup in appdata
            temp_dir = os.path.join(os.getenv('APPDATA'), 'HookLineSinker', 'temp')
            os.makedirs(temp_dir, exist_ok=True)
            temp_backup_dir = os.path.join(temp_dir, f'gdweave_backup_{int(time.time())}')
            os.makedirs(temp_backup_dir, exist_ok=True)

            # backup existing mods and configs
            mods_path = os.path.join(gdweave_path, 'Mods')
            configs_path = os.path.join(gdweave_path, 'configs')
            
            if os.path.exists(mods_path):
                shutil.copytree(mods_path, os.path.join(temp_backup_dir, 'Mods'))
                logging.info("Backed up Mods folder")
            
            if os.path.exists(configs_path):
                shutil.copytree(configs_path, os.path.join(temp_backup_dir, 'configs'))
                logging.info("Backed up configs folder")

            # download and install GDWeave
            self.set_status("Downloading GDWeave...")
            response = requests.get(gdweave_url)
            response.raise_for_status()
            
            zip_path = os.path.join(temp_dir, "GDWeave.zip")
            with open(zip_path, 'wb') as f:
                f.write(response.content)
            
            self.set_status("Installing GDWeave...")
            logging.info(f"Zip file downloaded to: {zip_path}")
            
            # extract the zip file
            extract_path = os.path.join(temp_dir, "GDWeave_extract")
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extractall(extract_path)
            logging.info(f"Zip file extracted to: {extract_path}")
            
            # remove existing GDWeave folder if it exists
            if os.path.exists(gdweave_path):
                logging.info(f"Removing existing GDWeave folder: {gdweave_path}")
                shutil.rmtree(gdweave_path)
            
            # move the extracted GDWeave folder to the correct location
            extracted_gdweave_path = os.path.join(extract_path, 'GDWeave')
            logging.info(f"Moving {extracted_gdweave_path} to {gdweave_path}")
            shutil.move(extracted_gdweave_path, gdweave_path)
            
            # copy winmm.dll to the game directory on Windows
            if sys.platform.startswith('win'):
                winmm_src = os.path.join(extract_path, 'winmm.dll')
                winmm_dst = os.path.join(game_path, 'winmm.dll')
                logging.info(f"Copying {winmm_src} to {winmm_dst}")
                shutil.copy2(winmm_src, winmm_dst)
            
            # restore mods and configs from backup
            if os.path.exists(os.path.join(temp_backup_dir, 'Mods')):
                shutil.copytree(os.path.join(temp_backup_dir, 'Mods'), os.path.join(gdweave_path, 'Mods'), dirs_exist_ok=True)
                logging.info("Restored Mods folder")
            
            if os.path.exists(os.path.join(temp_backup_dir, 'configs')):
                shutil.copytree(os.path.join(temp_backup_dir, 'configs'), os.path.join(gdweave_path, 'configs'), dirs_exist_ok=True)
                logging.info("Restored configs folder")

            self.settings['gdweave_version'] = self.get_gdweave_version()
            self.save_settings()
            self.set_status(f"GDWeave {self.settings['gdweave_version']} installed/updated successfully")
            self.update_setup_status()
            self.update_toggle_gdweave_button()
            logging.info("GDWeave installed/updated successfully!")

        except Exception as e:
            error_message = f"Failed to install/update GDWeave: {str(e)}"
            self.set_status(error_message)
            logging.info(error_message)
            logging.info(f"Error details: {traceback.format_exc()}")

        self.refresh_mod_lists()
    # updates the UI to reflect the current setup status
    def update_setup_status(self):
        # update step statuses
        self.update_step1_status()
        self.update_step2_status()
        self.update_step4_status()

        # update GDWeave button text
        if self.is_gdweave_installed():
            self.gdweave_button.config(text="Update GDWeave")
            self.gdweave_label.config(text="Updates GDWeave mod loader to the latest version. Will preserve your mods.")
        else:
            self.gdweave_button.config(text="Install GDWeave")
            self.gdweave_label.config(text="Installs GDWeave mod loader. Required for mod functionality.")


    # updates the text on the toggle GDWeave button
    def update_toggle_gdweave_button(self):
        if hasattr(self, 'toggle_gdweave_button'):
            new_label = self.get_initial_gdweave_label()
            self.toggle_gdweave_button.config(text=new_label)

    # determines the initial label for the GDWeave toggle button
    def get_initial_gdweave_label(self):
        if not self.settings.get('game_path'):
            return "Toggle GDWeave"
        
        gdweave_game_path = os.path.join(self.settings['game_path'], 'GDWeave')
        winmm_game_path = os.path.join(self.settings['game_path'], 'winmm.dll')
        
        if os.path.exists(gdweave_game_path) or os.path.exists(winmm_game_path):
            return "Disable GDWeave"
        else:
            return "Enable GDWeave"
            
    # checks if GDWeave is currently enabled
    def is_gdweave_enabled(self):
        if not self.settings.get('game_path'):
            return False
        game_path = self.settings['game_path']
        gdweave_game_path = os.path.join(game_path, 'GDWeave')
        if sys.platform.startswith('win'):
            return os.path.exists(gdweave_game_path) or os.path.exists(os.path.join(game_path, 'winmm.dll'))
        elif sys.platform.startswith('linux'):
            return os.path.exists(gdweave_game_path) or os.path.exists(os.path.join(game_path, 'run_game_with_gdweave.sh'))
        return False

    # updates the status of step 1 in the setup process
    def update_step1_status(self):
        if self.settings.get('game_path') and os.path.exists(self.settings['game_path']):
            self.step1_status.config(text="Verified", foreground="green")
        else:
            self.step1_status.config(text="Unverified", foreground="red")

    # updates the status of step 2 in the setup process
    def update_step2_status(self):
        if self.settings.get('game_path'):
            exe_path = os.path.join(self.settings['game_path'], 'webfishing.exe' if sys.platform.startswith('win') else 'webfishing.x86_64')
            if os.path.isfile(exe_path):
                self.step2_status.config(text="Verified", foreground="green")
            else:
                self.step2_status.config(text="Unverified", foreground="red")
        else:
            self.step2_status.config(text="Unverified", foreground="red")

    # updates the status of step 4 in the setup process
    def update_step4_status(self):
        try:
            if self.is_gdweave_installed():
                current_version = self.settings.get('gdweave_version', 'Unknown')
                latest_version = self.get_gdweave_version()
                if current_version == latest_version:
                    self.step4_status.config(text="Up to Date", foreground="green")
                else:
                    self.step4_status.config(text="Out of Date", foreground="orange")
            else:
                backup_path = os.path.join(self.app_data_dir, 'GDWeave_Backup')
                if os.path.exists(backup_path):
                    self.step4_status.config(text="Disabled (Backup Available)", foreground="orange")
                else:
                    self.step4_status.config(text="Uninstalled", foreground="red")
        except Exception as e:
            self.step4_status.config(text=f"Error: {str(e)}", foreground="red")

    # checks if the setup process is complete
    def is_setup_complete(self):
        return (
            self.settings.get('game_path') and
            os.path.exists(self.settings['game_path']) and
            self.check_dotnet(silent=True) and
            (self.is_gdweave_installed() or self.settings.get('gdweave_version'))
        )

    # checks if GDWeave is installed
    def is_gdweave_installed(self):
        if not self.settings.get('game_path'):
            return False
        gdweave_path = os.path.join(self.settings['game_path'], 'GDWeave')
        return os.path.exists(gdweave_path)
    
    # checks if .NET is installed on the system
    def check_dotnet(self, silent=False):
        try:
            subprocess.run(["dotnet", "--version"], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            if not silent:
                self.set_status(".NET is installed")
            return True
        except Exception as e:
            if not silent:
                self.set_status(f"Error: {str(e)}. .NET is not installed. Please install .NET 8.0 SDK from https://dotnet.microsoft.com/download")
            return False

    # opens the .NET download page in the default web browser
    def open_dotnet_download(self):
       webbrowser.open("https://dotnet.microsoft.com/download")

    # creates the help tab in the UI
    def create_help_tab(self):
        help_frame = ttk.Frame(self.notebook)
        self.notebook.add(help_frame, text="Troubleshooting")

        help_frame.grid_columnconfigure(0, weight=1)
        help_frame.grid_rowconfigure(2, weight=1)

        # title
        title_label = ttk.Label(help_frame, text="Troubleshooting Guide", font=("Helvetica", 16, "bold"))
        title_label.grid(row=0, column=0, pady=(20, 5), padx=20, sticky="w")

        # new subtitle
        subtitle_label = ttk.Label(help_frame, text="If you're experiencing any problems, please try all these steps first", font=("Helvetica", 10, "italic"))
        subtitle_label.grid(row=1, column=0, pady=(0, 10), padx=20, sticky="w")

        # create a canvas with a scrollbar
        canvas = tk.Canvas(help_frame)
        scrollbar = ttk.Scrollbar(help_frame, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)

        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(
                scrollregion=canvas.bbox("all")
            )
        )

        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.grid(row=2, column=0, sticky="nsew", padx=20, pady=10)
        scrollbar.grid(row=2, column=1, sticky="ns")

        # enable mousewheel scrolling
        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        canvas.bind_all("<MouseWheel>", _on_mousewheel)

        help_frame.grid_rowconfigure(2, weight=1)

        # help content
        help_items = [
            ("1. Install .NET 8.0 SDK Manually", "If you're having issues with .NET:\n- Visit the .NET Download Page\n- Download and install the .NET 8.0 SDK", "https://dotnet.microsoft.com/download"),
            ("2. Install GDWeave Manually", "If automatic GDWeave installation fails:\n- Go to GDWeave Releases\n- Download the latest GDWeave.zip\n- Extract it to your WEBFISHING game directory", "https://github.com/NotNite/GDWeave/releases"),
            ("3. Installing External Mods", "For mods not listed in our repository:\n- Use the 'Import ZIP Mod' feature in the Mod Manager tab\n- Select the .zip file of the mod you want to install\n- The mod will be automatically imported and installed", None),
            ("4. Run as Administrator (Windows)", "If you're having permission issues on Windows:\n- Right-click on Hook, Line, & Sinker executable\n- Select 'Run as administrator'", None),
            ("5. Verify Game Files", "If mods aren't working:\n- Verify your game files through Steam\n- Reinstall GDWeave", None),
            ("6. Check Antivirus Software", "Your antivirus might be blocking Hook, Line, & Sinker or mods:\n- Add an exception for the Hook, Line, & Sinker directory\n- Add an exception for your WEBFISHING game directory", None),
            ("7. Linux-Specific Issues", "If you're on Linux and having problems:\n- Ensure you have the necessary dependencies installed (e.g., mono-complete)\n- Check if you need to run the game with a specific command or script\n- Make sure you have the required permissions to access game files", None)
        ]

        for i, (title, content, link) in enumerate(help_items):
            item_frame = ttk.Frame(scrollable_frame)
            item_frame.grid(row=i, column=0, sticky="ew", padx=10, pady=5)
            item_frame.grid_columnconfigure(0, weight=1)

            ttk.Label(item_frame, text=title, font=("Helvetica", 12, "bold")).grid(row=0, column=0, sticky="w", pady=(5, 2))
            ttk.Label(item_frame, text=content, wraplength=500, justify="left").grid(row=1, column=0, sticky="w", padx=20)
            
            if link:
                ttk.Button(item_frame, text="Open Link", command=lambda url=link: webbrowser.open(url)).grid(row=2, column=0, sticky="w", padx=20, pady=(5, 0))

        # need more help section
        more_help_frame = ttk.Frame(scrollable_frame)
        more_help_frame.grid(row=len(help_items), column=0, sticky="ew", padx=10, pady=20)
        more_help_frame.grid_columnconfigure(0, weight=1)

        ttk.Label(more_help_frame, text="Need More Help?", font=("Helvetica", 12, "bold")).grid(row=0, column=0, sticky="w", pady=(5, 2))
        ttk.Label(more_help_frame, text="Visit our website for more information and updates.", wraplength=500, justify="left").grid(row=1, column=0, sticky="w", padx=20)

        # contact information
        contact_info = "If you're still having issues, please contact me:\n- Discord: @pyoid\n- Reddit: u/pyoid_loves_cats"
        ttk.Label(more_help_frame, text=contact_info, wraplength=500, justify="left").grid(row=2, column=0, sticky="w", padx=20, pady=(10, 0))

        # website button
        website_button = ttk.Button(help_frame, text="Visit Our Website", command=lambda: webbrowser.open("https://hooklinesinker.lol/"))
        website_button.grid(row=3, column=0, pady=(0, 20), padx=20, sticky="w")

    # makes links in a label clickable
    def make_links_clickable(self, label):
        text = label.cget("text")
        links = re.findall(r'\[([^\]]+)\]\(([^\)]+)\)', text)
        for link_text, url in links:
            text = text.replace(f'[{link_text}]({url})', link_text)
        label.config(text=text)
        
        def open_link(event):
            for link_text, url in links:
                if link_text in event.widget.cget("text"):
                    webbrowser.open(url)
                    break
        
        label.bind("<Button-1>", open_link)
        label.config(cursor="hand2", foreground="blue")

    # opens the Hook, Line, & Sinker folder
    def open_hls_folder(self):
        if sys.platform.startswith('win'):
            os.startfile(self.app_data_dir)
        elif sys.platform.startswith('linux'):
            subprocess.Popen(['xdg-open', self.app_data_dir])
        else:
            messagebox.showerror("Error", "Unsupported operating system")

    # opens the GDWeave folder
    def open_gdweave_folder(self):
        gdweave_path = os.path.join(self.settings['game_path'], 'GDWeave')
        if os.path.exists(gdweave_path):
            if sys.platform.startswith('win'):
                os.startfile(gdweave_path)
            else:
                messagebox.showerror("Error", "Unsupported operating system")
        else:
            messagebox.showerror("Error", "GDWeave folder not found. Make sure GDWeave is installed.")

    # opens the GDWeave log file
    def open_gdweave_log(self):
        log_path = os.path.join(self.settings['game_path'], 'GDWeave', 'GDWeave.log')
        if os.path.exists(log_path):
            with open(log_path, 'r') as f:
                log_content = f.read()
            
            log_window = tk.Toplevel(self.root)
            log_window.title("GDWeave Log")
            log_window.geometry("800x600")

            # set the window icon
            icon_path = os.path.join(os.path.dirname(__file__), 'icon.ico')
            if os.path.exists(icon_path):
                log_window.iconbitmap(icon_path)

            log_text = tk.Text(log_window, wrap=tk.WORD)
            log_text.pack(expand=True, fill='both')
            log_text.insert(tk.END, log_content)
            log_text.config(state='disabled')

            scrollbar = ttk.Scrollbar(log_text)
            scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
            log_text.config(yscrollcommand=scrollbar.set)
            scrollbar.config(command=log_text.yview)

            copy_button = ttk.Button(log_window, text="Copy to Clipboard", command=lambda: self.copy_to_clipboard(log_content))
            copy_button.pack(pady=10)
        else:
            messagebox.showerror("Error", "GDWeave log file not found. Make sure GDWeave is installed and has been run at least once.")

    # copies content to clipboard
    def copy_to_clipboard(self, content):
        self.root.clipboard_clear()
        self.root.clipboard_append(content)
        messagebox.showinfo("Success", "Log content copied to clipboard!")

    # removes all mods from the game's mods folder
    def clear_gdweave_mods(self):
        if not messagebox.askyesno(
            "Confirm Clear",
            "Are you sure you want to remove all mods from the game's mods folder? This action cannot be undone.",
        ):
            return
        gdweave_mods_path = os.path.join(self.settings['game_path'], 'GDWeave', 'Mods')
        if os.path.exists(gdweave_mods_path):
            try:
                for item in os.listdir(gdweave_mods_path):
                    item_path = os.path.join(gdweave_mods_path, item)
                    if os.path.isdir(item_path):
                        shutil.rmtree(item_path)
                    else:
                        os.remove(item_path)
                self.set_status("All mods have been removed from the game's mods folder.")
            except Exception as e:
                self.set_status(f"Error clearing GDWeave mods: {str(e)}")
        else:
            self.set_status("GDWeave mods folder not found.")

    # removes all mods managed by hook line & sinker
    def clear_hls_mods(self):
        if not messagebox.askyesno(
            "Confirm Clear",
            "Are you sure you want to remove all mods managed by Hook, Line, & Sinker? This action cannot be undone.",
        ):
            return
        try:
            # clear mods in appdata
            for item in os.listdir(self.mods_dir):
                item_path = os.path.join(self.mods_dir, item)
                if os.path.isdir(item_path):
                    shutil.rmtree(item_path)
                else:
                    os.remove(item_path)

            # clear mod cache
            self.mod_cache = {}
            self.save_mod_cache()

            # refresh mod lists
            self.refresh_mod_lists()

            self.set_status("All Hook, Line, & Sinker managed mods and cache have been cleared.")
        except Exception as e:
            self.set_status(f"Error clearing HLS mods: {str(e)}")

    # fetches the latest version from the server
    def update_latest_version_label(self):
        try:
            response = requests.get("https://hooklinesinker.lol/download/version.json")
            latest_version = response.json()['version']
            self.gui_queue.put(('latest_version', latest_version))
        except Exception as e:
            logging.info(f"Error fetching latest version: {str(e)}")
            self.gui_queue.put(('latest_version', 'Unknown'))

    # processes messages in the gui queue
    def process_gui_queue(self):
        try:
            while True:
                message = self.gui_queue.get_nowait()
                if message[0] == 'latest_version':
                    self.latest_version_label.config(text=f"Latest Version: {message[1]}")
        except queue.Empty:
            pass
        finally:
            # schedule the next queue check
            self.root.after(100, self.process_gui_queue)
            
    # checks for program updates and prompts user to update if available
    def check_for_program_updates(self, silent=False):
        try:
            response = requests.get("https://hooklinesinker.lol/download/version.json")
            version_data = response.json()
            remote_version = version_data['version']
            update_message = version_data.get('message', '')

            local_version = get_version()

            self.current_version_label.config(text=f"Current Version: {local_version}")
            self.latest_version_label.config(text=f"Latest Version: {remote_version}")

            if remote_version != local_version:
                if silent:
                    self.update_application(remote_version)
                    return True
                else:
                    message = f"A new version ({remote_version}) is available. You are currently on version {local_version}."
                    if update_message:
                        message += f"\n\n{update_message}"
                    message += "\n\nWould you like to update now?"
                    
                    should_update = messagebox.askyesno("Update Available", message)
                    if should_update:
                        self.update_application(remote_version)
                    return should_update
            elif not silent:
                messagebox.showinfo("Up to Date", "Hook, Line, & Sinker is up to date!")
            return False

        except Exception as e:
            error_message = f"Failed to check for updates: {str(e)}"
            self.set_status(error_message)
            logging.error(error_message)
            return False

    def update_available_mods_list(self):
        # clear current list
        self.available_listbox.delete(0, tk.END)
        
        # add mods to listbox sorted by title
        for mod in sorted(self.available_mods, key=lambda x: x['title']):
            display_title = self.get_display_name(mod['title'])
            self.available_listbox.insert(tk.END, display_title)

    def extract_mod_from_zip(self, zip_path, temp_dir):
        """Extract mod from zip file by finding manifest.json with Id field"""
        try:
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                # extract to temp directory
                zip_ref.extractall(temp_dir)
                
            # recursively search for manifest.json files
            manifest_files = []
            for root, _, files in os.walk(temp_dir):
                if 'manifest.json' in files:
                    manifest_path = os.path.join(root, 'manifest.json')
                    try:
                        # read the manifest to get the actual mod ID
                        with open(manifest_path, 'r') as f:
                            manifest = json.load(f)
                            if 'Id' in manifest:
                                mod_id = manifest['Id']
                                manifest_files.append((manifest_path, mod_id))
                    except (json.JSONDecodeError, KeyError):
                        continue
            
            if not manifest_files:
                raise ValueError("No valid manifest.json with Id field found in mod package")
                
            # use the first valid manifest found
            manifest_path, mod_id = manifest_files[0]
            mod_dir = os.path.dirname(manifest_path)
            
            # verify this is a mod directory
            if not os.path.exists(mod_dir):
                raise ValueError("Mod directory not found after extraction")
                
            return mod_dir
            
        except Exception as e:
            raise ValueError(f"Failed to extract mod: {str(e)}")

    def update_application(self, new_version):
        def download_and_install():
            try:
                self.set_status("Downloading update...")
                url = f"https://hooklinesinker.lol/download/{new_version}"
                response = requests.get(url, stream=True, allow_redirects=True)
                response.raise_for_status()

                temp_dir = os.path.join(os.getenv('APPDATA'), 'HookLineSinker', 'temp')
                os.makedirs(temp_dir, exist_ok=True)
                installer_path = os.path.join(temp_dir, f"HookLineSinker-Setup-{new_version}.exe")
                
                with open(installer_path, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)

                self.set_status("Update downloaded, launching installer...")
                if sys.platform.startswith('win'):
                    subprocess.Popen([installer_path])
                    
                    # save the new version to the config
                    self.settings['last_update_version'] = new_version
                    self.save_settings()

                    # inform the user and close the current instance
                    self.root.after(0, lambda: messagebox.showinfo(
                        "Update in Progress", 
                        "The update is being installed. Please restart the application to use the new version."
                    ))
                    self.root.after(0, self.root.quit)
                else:
                    self.root.after(0, lambda: messagebox.showinfo(
                        "Update Downloaded", 
                        f"The update has been downloaded to {installer_path}. Please install it manually."
                    ))

            except Exception as e:
                error_message = f"Failed to update: {str(e)}"
                self.root.after(0, lambda: messagebox.showerror("Update Failed", error_message))
                self.root.after(0, lambda: self.set_status(error_message))

        # Only start the download thread if we're actually updating
        threading.Thread(target=download_and_install, daemon=True).start()

    # creates and configures the status bar
    def create_status_bar(self):
        self.status_bar = ttk.Label(self.root, text="Ready", relief=tk.SUNKEN, anchor=tk.W)
        self.status_bar.pack(side=tk.BOTTOM, fill=tk.X)

    # updates the status bar with a new message
    def set_status(self, message):
        self.status_bar.config(text=message)
        self.root.update_idletasks()

    # clears placeholder text when entry widget is clicked
    def clear_placeholder(self, event, placeholder):
        if event.widget.get() == placeholder:
            event.widget.delete(0, tk.END)

    # restores placeholder text if entry widget is empty
    def restore_placeholder(self, event, placeholder):
        if event.widget.get() == "":
            event.widget.insert(0, placeholder)

    # opens a window to edit the configuration of a selected mod
    def edit_mod_config(self):
        selected = self.installed_listbox.curselection()
        if not selected:
            messagebox.showinfo("No Mod Selected", "Please select a mod to edit its configuration.")
            return

        if not self.settings.get('game_path'):
            messagebox.showerror("Error", "Game path not set. Please set the game path in the settings.")
            return

        mod = self.installed_mods[selected[0]]
        config_path = os.path.join(self.settings['game_path'], 'GDWeave', 'configs', f"{mod['id']}.json")

        if not os.path.exists(config_path):
            messagebox.showinfo("No Config Found", f"{mod['title']} doesn't have a config. Either this mod doesn't require one, or you need to restart your game to generate the config.")
            return

        try:
            with open(config_path, 'r') as f:
                config = json.load(f)
            
            if not config:  # if the config is empty treat it as if there's no file
                messagebox.showinfo("No Config Found", f"{mod['title']} doesn't have a config. Either this mod doesn't require one, or you need to restart your game to generate the config.")
                return
            
            self.open_config_editor(mod['title'], config, config_path)
        except json.JSONDecodeError:
            messagebox.showerror("Error", f"Failed to parse the configuration file for {mod['title']}.")
        except Exception as e:
            messagebox.showerror("Error", f"An error occurred while trying to edit the configuration: {str(e)}")

    # opens a window to edit the configuration of a mod
    def open_config_editor(self, mod_name, config, config_path):
        if not config:  # if the config is empty treat it as if there's no file
            messagebox.showinfo("No Config Found", f"{mod_name} doesn't have a config. Either this mod doesn't require one, or you need to restart your game to generate the config.")
            return

        editor_window = tk.Toplevel(self.root)
        editor_window.title(f"Edit Config: {mod_name}")
        editor_window.geometry("400x400")

        icon_path = os.path.join(os.path.dirname(__file__), 'icon.ico')
        if os.path.exists(icon_path):
            editor_window.iconbitmap(icon_path)

        frame = ttk.Frame(editor_window)
        frame.pack(expand=True, fill='both', padx=10, pady=10)

        canvas = tk.Canvas(frame)
        scrollbar = ttk.Scrollbar(frame, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)

        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(
                scrollregion=canvas.bbox("all")
            )
        )

        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        for i, (key, value) in enumerate(config.items()):
            ttk.Label(scrollable_frame, text=key).grid(row=i, column=0, sticky="w", padx=5, pady=2)
            
            if isinstance(value, bool):
                var = tk.BooleanVar(value=value)
                ttk.Checkbutton(scrollable_frame, variable=var, onvalue=True, offvalue=False).grid(row=i, column=1, sticky="w", padx=5, pady=2)
            elif isinstance(value, (int, float)):
                var = tk.StringVar(value=str(value))
                ttk.Entry(scrollable_frame, textvariable=var).grid(row=i, column=1, sticky="w", padx=5, pady=2)
            else:
                var = tk.StringVar(value=str(value))
                ttk.Entry(scrollable_frame, textvariable=var).grid(row=i, column=1, sticky="w", padx=5, pady=2)
            
            config[key] = var

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        def save_config():
            try:
                new_config = {}
                for k, v in config.items():
                    value = v.get()
                    if isinstance(value, str):
                        # try to convert string to int or float if possible
                        try:
                            value = int(value)
                        except ValueError:
                            try:
                                value = float(value)
                            except ValueError:
                                pass  # keep it as a string if it's not a number
                    new_config[k] = value
                
                with open(config_path, 'w') as f:
                    json.dump(new_config, f, indent=2)
                messagebox.showinfo("Success", f"Configuration for {mod_name} has been updated.")
                editor_window.destroy()
            except Exception as e:
                messagebox.showerror("Error", f"Failed to save configuration: {str(e)}")

        def restore_defaults():
            if messagebox.askyesno("Restore Defaults", 
                                 "Are you sure you want to restore defaults? This is irreversible!"):
                try:
                    os.remove(config_path)
                    messagebox.showinfo("Success", 
                                      "Configuration has been reset. Please restart your game for the defaults to take effect.")
                    editor_window.destroy()
                except Exception as e:
                    messagebox.showerror("Error", f"Failed to restore defaults: {str(e)}")

        button_frame = ttk.Frame(editor_window)
        button_frame.pack(pady=10)
        
        ttk.Button(button_frame, text="Save", command=save_config).pack(side="left", padx=5)
        ttk.Button(button_frame, text="Restore Defaults", command=restore_defaults).pack(side="left", padx=5)
    def show_context_menu(self, event):
        listbox = event.widget
        index = listbox.nearest(event.y)
        
        menu = tk.Menu(self.root, tearoff=0)
        
        if index != -1:
            listbox.selection_clear(0, tk.END)
            listbox.selection_set(index)
            listbox.activate(index)
            
            if listbox == self.available_listbox:
                # Simple menu for available mods
                menu.add_command(label="Install", command=self.install_mod)
                
            elif listbox == self.installed_listbox:
                mod = self.installed_mods[index]
                
                # Basic mod management options
                menu.add_command(label="Edit Config", command=self.edit_mod_config)
                menu.add_command(label="Test Mod", command=lambda: self.test_mod(mod))
                menu.add_separator()
                
                # Mod state controls
                menu.add_command(label="Enable", command=self.enable_mod)
                menu.add_command(label="Disable", command=self.disable_mod)
                menu.add_command(label="Uninstall", command=self.uninstall_mod)
                
                # Version management (non-third-party mods only)
                if not mod.get('third_party', False):
                    menu.add_separator()
                    version_menu = tk.Menu(menu, tearoff=0)
                    menu.add_cascade(label="Change Version", menu=version_menu)
                    
                    versions = self.get_mod_versions(mod)
                    if versions:
                        current_version = mod.get('version', 'Unknown')
                        for version in versions[:3]:
                            version_number = version['version_number']
                            label = f"v{version_number}"
                            if version_number == current_version:
                                label += " (Current)"
                            version_menu.add_command(
                                label=label,
                                command=lambda v=version: self.install_specific_version(mod, v),
                                state='disabled' if version_number == current_version else 'normal'
                            )
                    else:
                        version_menu.add_command(label="No versions available", state="disabled")
                
                # Third-party mod options
                if mod.get('third_party', False):
                    menu.add_separator()
                    menu.add_command(label="Export as ZIP", command=lambda: self.export_mod_as_zip(mod))

            menu.tk_popup(event.x_root, event.y_root)
    def get_mod_versions(self, mod):
        try:
            if not mod.get('thunderstore_id'):
                return []

            # Get all mods from thunderstore API
            response = requests.get("https://thunderstore.io/c/webfishing/api/v1/package/")
            response.raise_for_status()
            all_mods = response.json()

            # Find the matching mod
            mod_data = next(
                (m for m in all_mods if f"{m['owner']}-{m['name']}" == mod['thunderstore_id']),
                None
            )

            if not mod_data:
                return []

            # Sort versions by date created
            versions = sorted(
                mod_data['versions'],
                key=lambda x: x['date_created'],
                reverse=True
            )[:3]  # Get latest 3 versions

            return versions

        except Exception as e:
            logging.error(f"Error fetching versions for {mod['title']}: {str(e)}")
            return []

    def install_specific_version(self, mod, version):
        try:
            # Create temporary mod info for installation
            temp_mod = mod.copy()
            temp_mod.update({
                'version': version['version_number'],
                'download': version['download_url'],
                'dependencies': version['dependencies']
            })
            
            # Confirm with user
            if messagebox.askyesno(
                "Install Specific Version",
                f"Are you sure you want to install v{version['version_number']} of {mod['title']}?\n\n"
                "This will replace the current version."
            ):
                self.download_and_install_mod(temp_mod)
        except Exception as e:
            error_message = f"Failed to install version {version['version_number']}: {str(e)}"
            self.set_status(error_message)
            messagebox.showerror("Error", error_message)

    def test_mod(self, mod):
        try:
            # check dependencies first
            dependencies = self.check_mod_dependencies(mod)

            # disable all mods first
            for installed_mod in self.installed_mods:
                if installed_mod.get('enabled', True):
                    installed_mod['enabled'] = False
                    self.update_mod_status_in_listbox(installed_mod)
                    self.save_mod_status(installed_mod)
                    self.remove_mod_from_game(installed_mod)

            # enable the selected mod and its dependencies
            mods_to_enable = [mod]

            # find and add dependencies to enable list if there are any
            if dependencies:
                for dep_id in dependencies:
                    if dep_mod := next(
                        (m for m in self.installed_mods if m['id'] == dep_id), None
                    ):
                        mods_to_enable.append(dep_mod)

            # enable all required mods
            for mod_to_enable in mods_to_enable:
                mod_to_enable['enabled'] = True
                self.update_mod_status_in_listbox(mod_to_enable)
                self.save_mod_status(mod_to_enable)
                self.copy_mod_to_game(mod_to_enable)

            self.refresh_mod_lists()

            # update status message to show enabled dependencies
            if len(mods_to_enable) > 1:
                dep_names = ", ".join(m['title'] for m in mods_to_enable[1:])
                self.set_status(f"Test mode enabled for {mod['title']} with dependencies: {dep_names}")
                messagebox.showinfo("Test Mode", f"Mod test mode enabled for {mod['title']} and its dependencies: {dep_names}")
            else:
                self.set_status(f"Test mode enabled for: {mod['title']}")
                messagebox.showinfo("Test Mode", "Mod test mode enabled. All other mods have been disabled.")

        except Exception as e:
            error_message = f"Failed to enable test mode: {str(e)}"
            self.set_status(error_message)
            messagebox.showerror("Error", error_message)

    def export_mod_as_zip(self, mod):
        try:
            # determine source directory
            mod_dir = os.path.join(self.mods_dir, "3rd_party", mod['id'])
            if not os.path.exists(mod_dir):
                messagebox.showerror("Error", "Mod directory not found.")
                return
                
            # ask user where to save the zip
            zip_path = filedialog.asksaveasfilename(
                defaultextension=".zip",
                filetypes=[("ZIP files", "*.zip")],
                initialfile=f"{mod['title']}.zip"
            )
            
            if not zip_path:
                return
                
            self.set_status(f"Exporting {mod['title']} as ZIP...")
            
            with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                for root, dirs, files in os.walk(mod_dir):
                    for file in files:
                        if file != 'mod_info.json':  # exclude mod_info.json
                            file_path = os.path.join(root, file)
                            arcname = os.path.relpath(file_path, mod_dir)
                            zipf.write(file_path, arcname)
            
            self.set_status(f"Successfully exported {mod['title']} to {zip_path}")
            messagebox.showinfo("Success", f"Mod exported successfully to:\n{zip_path}")
            
        except Exception as e:
            error_message = f"Failed to export mod: {str(e)}"
            self.set_status(error_message)
            messagebox.showerror("Error", error_message)

    # enables selected mods
    def enable_mod(self):
        if not self.check_setup():
            return
        if selected := self.installed_listbox.curselection():
            for index in selected:
                mod = self.installed_mods[index]
                mod['enabled'] = True
                self.update_mod_status_in_listbox(mod)
                self.save_mod_status(mod)
                self.copy_mod_to_game(mod)
                logging.info(f"Enabled mod: {mod['title']} (ID: {mod['id']}, Third Party: {mod.get('third_party', False)})")
            self.refresh_mod_lists()
            self.set_status(f"Enabled {len(selected)} mod(s)")
                
    # copies a third-party mod to the game directory
    def copy_third_party_mod_to_game(self, mod):
        src_path = os.path.join(self.mods_dir, "3rd_party", mod['id'])
        dst_path = os.path.join(self.settings['game_path'], 'GDWeave', 'Mods', mod['id'])
        shutil.copytree(src_path, dst_path, dirs_exist_ok=True)
        self.set_status(f"Installed 3rd party mod: {mod['title']}")
        self.refresh_mod_lists()

    # uninstalls selected mods
    def uninstall_mod(self):
        if selected := self.installed_listbox.curselection():
            for index in selected:
                mod = self.installed_mods[index]
                self.set_status(f"Uninstalling mod: {mod['title']}")
                try:
                    self.uninstall_mod_files(mod)
                except Exception as e:
                    error_message = f"Failed to uninstall mod {mod['title']}: {str(e)}"
                    self.set_status(error_message)
            self.refresh_mod_lists()

    # removes mod files from the system
    def uninstall_mod_files(self, mod):
        if mod.get('third_party', False):
            mod_path = os.path.join(self.mods_dir, "3rd_party", mod['id'])
        else:
            mod_path = os.path.join(self.mods_dir, mod['id'])
        
        if os.path.exists(mod_path):
            shutil.rmtree(mod_path)
        
        # remove from game directory if it exists
        game_mod_path = os.path.join(self.settings['game_path'], 'GDWeave', 'Mods', mod['id'])
        if os.path.exists(game_mod_path):
            shutil.rmtree(game_mod_path)
        
        self.set_status(f"Uninstalled mod: {mod['title']}")

    # enables selected mods
    def enable_mod(self):
        if not self.check_setup():
            return
        if selected := self.installed_listbox.curselection():
            enabled_count = 0
            for index in selected:
                mod = self.installed_mods[index]
                if not mod.get('enabled', True):
                    mod['enabled'] = True
                    self.update_mod_status_in_listbox(mod)
                    self.save_mod_status(mod)
                    self.copy_mod_to_game(mod)
                    enabled_count += 1
                    logging.info(f"Enabled mod: {mod['title']} (ID: {mod['id']}, Third Party: {mod.get('third_party', False)})")

            if enabled_count > 0:
                self.refresh_mod_lists()
                self.set_status(f"Enabled {enabled_count} mod(s)")
            else:
                self.set_status("No mods were enabled. Selected mods may already be enabled.")

    # disables selected mods
    def disable_mod(self):
        if not self.check_setup():
            return
        if selected := self.installed_listbox.curselection():
            for index in selected:
                mod = self.installed_mods[index]
                mod['enabled'] = False
                self.update_mod_status_in_listbox(mod)
                self.save_mod_status(mod)
                self.remove_mod_from_game(mod)
            self.refresh_mod_lists()
            self.set_status(f"Disabled {len(selected)} mod(s)")

    # creates a mod.json file for imported mods
    def create_mod_json(self, mod_folder, mod_name):
        mod_info = {
            'title': mod_name,
            'author': 'Unknown',
            'description': 'Imported mod',
            'enabled': True,
            'version': 'Unknown'
        }
        with open(os.path.join(mod_folder, 'mod.json'), 'w') as f:
            json.dump(mod_info, f)

    # checks if the game path is set and valid
    def check_setup(self):
        if not self.settings.get('game_path') or not os.path.exists(self.settings.get('game_path')):
            messagebox.showinfo("Setup Required", "Please follow all the steps for installation in the Game Manager tab.")
            self.notebook.select(2)  # switch to hls setup tab
            return False
        return True

    # updates the status of a mod in the installed mods listbox
    def update_mod_status_in_listbox(self, mod):
        index = self.installed_mods.index(mod)
        status = "✅" if mod.get('enabled', True) else "❌"
        third_party = "[3rd] " if mod.get('third_party', False) else "" 
        self.installed_listbox.delete(index)
        self.installed_listbox.insert(index, f"{status} {third_party}{mod['title']}".strip())

    # shows a prompt to join the discord community
    def show_discord_prompt(self):
        if not self.settings.get('discord_prompt_shown', False):
            if response := messagebox.askyesno(
                "Join Our Discord Community",
                "Welcome to Hook, Line, & Sinker!\n\n"
                "We highly recommend joining our Discord community for:\n"
                "• Troubleshooting assistance (only place I can help!)\n"
                "• Latest updates and announcements\n"
                "• Mod discussions and sharing\n"
                "• Direct support from the developer\n\n"
                "Would you like to join our Discord now?",
                icon='info',
            ):
                webbrowser.open("https://discord.gg/HzhCPxeCKY")

            self.settings['discord_prompt_shown'] = True
            self.save_settings()

    # saves the status of a mod to its mod_info.json file
    def save_mod_status(self, mod):
        if mod.get('third_party', False):
            mod_folder = os.path.join(self.mods_dir, "3rd_party", mod['id'])
        else:
            mod_folder = os.path.join(self.mods_dir, mod['id'])
        
        mod_json_path = os.path.join(mod_folder, 'mod_info.json')
        
        if not os.path.exists(mod_folder):
            os.makedirs(mod_folder)
        
        try:
            with open(mod_json_path, 'w') as f:
                json.dump(mod, f, indent=2)
            logging.info(f"Saved mod status for {mod['title']} (ID: {mod['id']})")
        except Exception as e:
            error_message = f"Failed to save mod status for {mod['title']} (ID: {mod['id']}): {str(e)}"
            self.set_status(error_message)
            logging.info(error_message)

        self.save_mod_cache()

    # loads the mod cache from file
    def load_mod_cache(self):
        try:
            if os.path.exists(self.mod_cache_file):
                with open(self.mod_cache_file, 'r') as f:
                    self.mod_cache = json.load(f)
            else:
                self.mod_cache = {}
        except Exception as e:
            error_message = f"Failed to load mod cache: {str(e)}"
            self.set_status(error_message)
            self.mod_cache = {}  # set to empty dict in case of error
    # updates the mod details display when a mod is selected
    def update_mod_details(self, event):
        selected_listbox = event.widget
        selected = selected_listbox.curselection()
        if not selected:
            return

        index = selected[0]
        display_title = selected_listbox.get(index)

        # clear previous details and widgets
        self.mod_details.config(state='normal')
        self.mod_details.delete('1.0', tk.END)
        
        # remove any existing buttons
        for widget in self.mod_details_frame.winfo_children():
            if isinstance(widget, ttk.Button):
                widget.destroy()

        # handle category headers
        if display_title.startswith('-- '):
            self._show_category_details(display_title)
            return
        try:
            # clean title and get mod info
            clean_title = display_title.replace('✅', '').replace('❌', '').replace('[3rd]', '').strip()
            backend_title = self.get_backend_name(clean_title)
            mod_list = self.available_mods if selected_listbox == self.available_listbox else self.installed_mods
            mod = next((m for m in mod_list if m['title'].strip() == backend_title), None)

            if not mod:
                raise ValueError(f"no mod found with title: {backend_title}")

            # title section with status indicators
            display_title = self.get_display_name(mod['title'])
            title_text = f"{display_title} v{mod.get('version', '?')}\n"
            title_text += f"by {mod.get('author', 'Unknown')}\n\n"
            self.mod_details.insert(tk.END, title_text, "header")
            self.mod_details.tag_config("header", font=("TkDefaultFont", 10, "bold"))

            # stats section
            stats = []
            if 'last_updated' in mod:
                updated = self._format_timestamp(mod['last_updated'])
                if updated:
                    stats.append(f"📅 Updated {updated}")
            if 'downloads' in mod:
                stats.append(f"🌐 {mod['downloads']:,} downloads")
            if 'likes' in mod:
                stats.append(f"👍 {mod['likes']:,} likes")
            if stats:
                self.mod_details.insert(tk.END, " • ".join(stats) + "\n")
            # categories section (use single character emojis or it breaks)
            if categories := mod.get('categories', []):
                category_display = []
                category_emojis = {
                    'Mods': '🎯',
                    'Cosmetics': '🎨',
                    'Tools': '🔨',
                    'Libraries': '📖',
                    'Misc': '📦',
                    'Client Side': '💻',
                    'Server Side': '🖥',
                    'Fish': '🐟',
                    'Species': '🦈',
                    'Maps': '🗺'
                }
                for category in categories:
                    emoji = category_emojis.get(category, '📦')  # default emoji if category not found
                    category_display.append(f"{emoji} {category}")
                self.mod_details.insert(tk.END, " • ".join(category_display) + "\n")

            # content warnings section
            warnings = []
            if mod.get('has_nsfw_content', False):
                warnings.append("🔞 NSFW")
            if mod.get('is_deprecated', False):
                warnings.append("⚠️ Deprecated")
            if mod.get('third_party', False):
                warnings.append("⚠️ Third Party Mod")
            if warnings:
                self.mod_details.insert(tk.END, " • ".join(warnings) + "\n\n")
            elif stats or categories:
                self.mod_details.insert(tk.END, "\n")

            # description
            if mod.get('third_party', False):
                self.mod_details.insert(tk.END, "Description:\n", "subheader")
                if mod.get('description'):
                    self.mod_details.insert(tk.END, f"{mod['description']}\n\n")
                else:
                    self.mod_details.insert(tk.END, f"We don't know much about the 3rd party mod {display_title}, but we're sure it's great!\n\n")
            elif mod.get('description'):
                desc = strip_tags(mod['description']) or mod['description']
                self.mod_details.insert(tk.END, "Description:\n", "subheader")
                self.mod_details.insert(tk.END, f"{desc}\n\n")

            # dependencies section
            if deps := mod.get('dependencies', []):
                self.mod_details.insert(tk.END, "Dependencies:\n", "subheader")
                self.mod_details.tag_config("subheader", font=("TkDefaultFont", 9, "bold"))
                for dep in deps:
                    # parse creator-title-version format
                    parts = dep.split('-')
                    if len(parts) == 3:
                        creator, title, version = parts
                        formatted_dep = f"{title} ({version}) by {creator}"
                        self.mod_details.insert(tk.END, f"• {formatted_dep}\n")
                    else:
                        self.mod_details.insert(tk.END, f"• {dep}\n")
                self.mod_details.insert(tk.END, "\n")

            # create button frame using grid
            button_frame = ttk.Frame(self.mod_details_frame)
            button_frame.grid(row=1, column=0, columnspan=2, sticky="w", padx=5, pady=5)

            # always construct thunderstore url from thunderstore_id
            if mod.get('thunderstore_id'):
                creator, mod_name = mod['thunderstore_id'].split('-', 1)
                url = f"https://thunderstore.io/c/webfishing/p/{creator}/{mod_name}/"
                ttk.Button(
                    button_frame,
                    text="View More Information on Thunderstore",
                    command=lambda url=url: webbrowser.open(url)
                ).grid(row=0, column=0, padx=2)

        except Exception as e:
            error_msg = f"Error: Unable to find mod details for '{display_title}'. Error: {str(e)}"
            self.mod_details.insert(tk.END, error_msg)
            logging.error(f"Error in update_mod_details: {error_msg}")

        self.mod_details.config(state='disabled')

    # checks if a thunderstore mod is installed and enabled
    def is_thunderstore_mod_enabled(self, thunderstore_id):
        try:
            # check installed mods list first
            for mod in self.installed_mods:
                # skip third party mods
                if mod.get('third_party', False):
                    continue
                    
                # check if thunderstore_id matches and mod is enabled
                if mod.get('thunderstore_id') == thunderstore_id and mod.get('enabled', False):
                    return True
                    
            # check mods directory as backup
            for mod_folder in os.listdir(self.mods_dir):
                # skip 3rd party folder
                if mod_folder == '3rd_party':
                    continue
                    
                mod_info_path = os.path.join(self.mods_dir, mod_folder, 'mod_info.json')
                if os.path.exists(mod_info_path):
                    with open(mod_info_path, 'r') as f:
                        mod_info = json.load(f)
                        # check if thunderstore_id matches and mod is enabled
                        if mod_info.get('thunderstore_id') == thunderstore_id and mod_info.get('enabled', False):
                            return True
                            
            return False
            
        except Exception as e:
            logging.error(f"Error checking if thunderstore mod {thunderstore_id} is enabled: {str(e)}")
            return False



    # verifies the game installation path
    def verify_installation(self):
        try:
            game_path = self.game_path_entry.get()
            exe_name = 'webfishing.exe' if platform.system() == 'Windows' else 'webfishing'
            exe_path = os.path.join(game_path, exe_name)
            if os.path.exists(game_path) and os.path.isfile(exe_path):
                self.set_status("Game installation verified successfully!")
            else:
                self.set_status(f"Invalid game installation path or {exe_name} not found!")
        except Exception as e:
            error_message = f"Error verifying game installation: {str(e)}"
            self.set_status(error_message)

    # loads user settings from json file
    def load_settings(self):
        settings_path = os.path.join(self.app_data_dir, 'settings.json')
        if os.path.exists(settings_path):
            with open(settings_path, 'r') as f:
                self.settings = json.load(f)
        else:
            self.settings = {}
        
        # set default value for discord prompt if it doesn't exist
        if 'discord_prompt_shown' not in self.settings:
            self.settings['discord_prompt_shown'] = False

        # set default value for no_logging if it doesn't exist
        if 'no_logging' not in self.settings:
            self.settings['no_logging'] = False

        # set default value for error_reporting_prompted if it doesn't exist
        if 'error_reporting_prompted' not in self.settings:
            self.settings['error_reporting_prompted'] = False
        
        self.print_settings()

    # saves current user settings to json file
    def save_settings(self):
        self.settings.update({
            "auto_update": self.auto_update.get(),
            "windowed_mode": self.windowed_mode.get(),
            "notifications": self.notifications.get(),
            "theme": self.theme.get(),
            "game_path": self.game_path_entry.get(),
            "show_nsfw": self.show_nsfw.get(),
            "show_deprecated": self.show_deprecated.get()
        })
        settings_path = os.path.join(self.app_data_dir, 'settings.json')
        with open(settings_path, 'w') as f:
            json.dump(self.settings, f)
        self.set_status("Settings saved successfully!")
        logging.info("Settings saved:", self.settings)
    # updates the ui lists of available and installed mods
    def refresh_mod_lists(self):
        if hasattr(self, 'available_listbox'):
            # preserve the current items in the listbox
            current_items = list(self.available_listbox.get(0, tk.END))
            
            # only update if the list is empty (first load)
            if not current_items:
                self.load_available_mods()

        self.installed_mods = self.get_installed_mods()
        
        # something here is seriously fucked up and i give up, i'll fix in 1.1.7, edit: i'll fix in 1.2.1
        if hasattr(self, 'installed_listbox'):
            self.installed_listbox.delete(0, tk.END)
            for mod in self.installed_mods:
                status = "✅" if mod.get('enabled', True) else "❌"
                third_party = "[3rd]" if mod.get('third_party', False) else ""
                display_title = self.get_display_name(mod['title'])
                display_text = f"{status} {third_party} {display_title}".strip()
                self.installed_listbox.insert(tk.END, display_text)

        # update the mod cache
        self.save_mod_cache()
        
        # refresh the lists with current filters
        self.filter_available_mods()
        self.filter_installed_mods()

    # removes non-existent mods from the cache
    def clean_mod_cache(self):
        updated_cache = {
            mod_id: mod_info
            for mod_id, mod_info in self.mod_cache.items()
            if self.mod_exists(
                {'id': mod_id, 'third_party': mod_info.get('third_party', False)}
            )
        }
        self.mod_cache = updated_cache
        self.save_mod_cache()

    # retrieves list of installed mods from the mods directory
    def get_installed_mods(self):
        installed_mods = []
        
        # check official mods
        for mod_folder in os.listdir(self.mods_dir):
            if mod_folder != "3rd_party":
                mod_info_path = os.path.join(self.mods_dir, mod_folder, 'mod_info.json')
                if os.path.exists(mod_info_path):
                    with open(mod_info_path, 'r') as f:
                        mod_info = json.load(f)
                        installed_mods.append(mod_info)

        # check third-party mods
        third_party_mods_dir = os.path.join(self.mods_dir, "3rd_party")
        if os.path.exists(third_party_mods_dir):
            for mod_folder in os.listdir(third_party_mods_dir):
                mod_info_path = os.path.join(third_party_mods_dir, mod_folder, 'mod_info.json')
                if os.path.exists(mod_info_path):
                    with open(mod_info_path, 'r') as f:
                        mod_info = json.load(f)
                        mod_info['third_party'] = True
                        installed_mods.append(mod_info)

        return installed_mods

    # downloads and installs a mod
    def download_and_install_mod(self, mod, install=True):
        # Create a thread to handle the download and installation
        thread = threading.Thread(
            target=self._download_and_install_mod_thread,
            args=(mod, install)
        )
        thread.daemon = True
        thread.start()
        
    def _download_and_install_mod_thread(self, mod, install=True):
        download_temp_dir = None
        try:
            self.mod_downloading = True
            self.set_status_safe(f"Downloading {mod['title']}...")
            
            # create temp directory
            temp_dir = os.path.join(self.app_data_dir, 'temp')
            os.makedirs(temp_dir, exist_ok=True)
            
            # create unique temp directory with uuid
            download_temp_dir = os.path.join(temp_dir, f"download_{uuid.uuid4().hex}")
            os.makedirs(download_temp_dir)
            
            # download the mod file with error handling
            try:
                response = requests.get(mod['download'], timeout=30)
                response.raise_for_status()
            except requests.Timeout:
                raise ValueError("Download timed out - please try again")
            except requests.RequestException as e:
                raise ValueError(f"Download failed: {str(e)}")
            
            zip_path = os.path.join(download_temp_dir, f"{mod['id']}.zip")
            try:
                with open(zip_path, 'wb') as f:
                    f.write(response.content)
            except IOError as e:
                raise ValueError(f"Failed to save downloaded file: {str(e)}")
                
            # extract the zip
            extract_dir = os.path.join(download_temp_dir, 'extracted')
            os.makedirs(extract_dir)
            
            try:
                with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                    zip_ref.extractall(extract_dir)
            except zipfile.BadZipFile:
                raise ValueError("Downloaded file is not a valid zip archive")
            except Exception as e:
                raise ValueError(f"Failed to extract zip file: {str(e)}")
                
            # find manifest.json with valid id field
            manifest_path = None
            manifest = None
            for root, dirs, files in os.walk(extract_dir):
                if 'manifest.json' in files:
                    try:
                        with open(os.path.join(root, 'manifest.json'), 'r') as f:
                            manifest_data = json.load(f)
                            if manifest_data.get('Id'):
                                manifest_path = os.path.join(root, 'manifest.json')
                                manifest = manifest_data
                                break
                    except json.JSONDecodeError:
                        continue
                    except IOError:
                        continue
                        
            if not manifest_path or not manifest:
                raise ValueError(f"{mod['title']} is likely not an installable mod!")
                
            # get the mod id from manifest
            mod_id = manifest.get('Id')
            if not mod_id:
                raise ValueError(f"{mod['title']} is likely not an installable mod!")
                
            # create the final mod directory
            mod_dir = os.path.join(self.mods_dir, mod_id)
            if os.path.exists(mod_dir):
                try:
                    shutil.rmtree(mod_dir)
                except Exception as e:
                    raise ValueError(f"Failed to remove existing mod directory: {str(e)}")
                
            # move the mod files
            try:
                manifest_parent = os.path.dirname(manifest_path)
                if manifest_parent != extract_dir:
                    shutil.move(manifest_parent, mod_dir)
                else:
                    shutil.move(extract_dir, mod_dir)
            except Exception as e:
                raise ValueError(f"Failed to move mod files: {str(e)}")
                
            # create mod_info.json
            mod_info = {
                'id': mod_id,
                'title': manifest.get('Name', mod['title']),
                'author': manifest.get('Author', mod['author']),
                'description': manifest.get('Description', mod['description']),
                'version': manifest.get('Version', mod['version']),
                'enabled': True,
                'thunderstore_id': mod['thunderstore_id']
            }
            
            try:
                mod_info_path = os.path.join(mod_dir, 'mod_info.json')
                with open(mod_info_path, 'w') as f:
                    json.dump(mod_info, f, indent=2)
            except Exception as e:
                raise ValueError(f"Failed to create mod_info.json: {str(e)}")
                
            # add to installed mods
            self.installed_mods.append(mod_info)
            
            # copy to game if enabled
            if mod_info['enabled']:
                try:
                    self.copy_mod_to_game(mod_info)
                except Exception as e:
                    raise ValueError(f"Failed to copy mod to game directory: {str(e)}")
                
            self.set_status_safe(f"Successfully installed {mod['title']}")
            logging.info(f"Installed mod: {mod['title']} (ID: {mod_id})")

            if install:
                self.root.after(0, self.installation_complete, mod_info)
            else:
                return mod_info
                
        except Exception as e:
            error_message = f"Failed to install {mod['title']}: {str(e)}"
            self.set_status_safe(error_message)
            logging.error(error_message)
            if install:
                self.root.after(0, self.installation_failed, error_message)
            else:
                raise ValueError(error_message)
        finally:
            self.mod_downloading = False
            # clean up temp directory
            if download_temp_dir and os.path.exists(download_temp_dir):
                try:
                    shutil.rmtree(download_temp_dir)
                except Exception as e:
                    logging.error(f"Failed to clean up temp directory: {str(e)}")

    # called when mod installation is complete
    def installation_complete(self, mod_info):
        self.set_status_safe(f"Mod {mod_info['title']} version {mod_info['version']} installed successfully!")
        self.refresh_mod_lists()
        self.copy_mod_to_game(mod_info)

    def download_file(self, url, destination):
        try:
            response = requests.get(url, stream=True)
            response.raise_for_status()
            
            # get file size if available
            total_size = int(response.headers.get('content-length', 0))
            
            return True
        except Exception as e:
            error_message = f"Failed to download file from {url}: {str(e)}"
            logging.error(error_message)
            raise ValueError(error_message)

    # installs a previously downloaded mod
    def install_downloaded_mod(self, mod_info):
        # move the downloaded mod to the mods directory
        mod_path = os.path.join(self.mods_dir, mod_info['id'])
        os.makedirs(mod_path, exist_ok=True)
        
        # save mod_info.json
        with open(os.path.join(mod_path, 'mod_info.json'), 'w') as f:
            json.dump(mod_info, f, indent=2)
        
        # copy mod files to game directory
        self.copy_mod_to_game(mod_info)
        
        # add to installed mods list
        self.installed_mods.append(mod_info)
        
        self.set_status(f"Installed mod: {mod_info['title']}")
        self.installation_complete(mod_info)

    # verifies the contents of the app data mods directory
    def verify_appdata_mods(self):
        logging.info("Verifying contents of app data mods directory")
        for mod_id in os.listdir(self.mods_dir):
            mod_path = os.path.join(self.mods_dir, mod_id)
            if os.path.isdir(mod_path):
                logging.info(f"Mod directory: {mod_id}")
                for root, dirs, files in os.walk(mod_path):
                    for file in files:
                        logging.info(f"  - {os.path.join(os.path.relpath(root, mod_path), file)}")
                        
    # called when mod installation is complete
    def installation_complete(self, mod_info):
        self.set_status(f"Mod {mod_info['title']} version {mod_info['version']} installed successfully!")
        self.refresh_mod_lists()
        self.verify_appdata_mods() 
        self.copy_mod_to_game(mod_info)

    # called when mod installation fails
    def installation_failed(self, error_message):
        self.set_status_safe(f"Failed to install mod: {error_message}")

    # retrieves the version information for a mod
    def get_mod_version(self, mod):
        try:
            url = mod['download']
            parsed_url = urlparse(url)

            if 'github.com' in parsed_url.netloc:
                # github url
                repo_owner, repo_name = parsed_url.path.split('/')[1:3]
                api_url = f"https://api.github.com/repos/{repo_owner}/{repo_name}/releases/latest"
            else:
                # assume gitea url
                base_url = f"{parsed_url.scheme}://{parsed_url.netloc}"
                path_parts = parsed_url.path.split('/')
                repo_owner, repo_name = path_parts[1:3]
                api_url = f"{base_url}/api/v1/repos/{repo_owner}/{repo_name}/releases/latest"

            response = requests.get(api_url)
            response.raise_for_status()
            data = response.json()

            # extract version from tag_name
            version = re.search(r'v?(\d+\.\d+\.\d+)', data['tag_name'])
            version = version[1] if version else data['tag_name']

            return {
                'version': version,
                'published_at': data['published_at']
            }
        except Exception as e:
            logging.info(f"Failed to get version: {str(e)}")
            return {
                'version': "Unknown",
                'published_at': None
            }
    # checks for updates to the program mods and gdweave
    def check_for_updates(self, silent=False):
        try:
            program_updated = self.check_for_program_updates()
            # check for mod updates
            self.set_status_safe("Checking for mod and GDWeave updates...")
            updates_available = False

            if not self.installed_mods:
                self.set_status_safe("No mods installed. Skipping mod update check.")
            else:
                # First pass - collect all mods that need updates
                mods_to_update = []
                for installed_mod in self.installed_mods:
                    for available_mod in self.available_mods:
                        if installed_mod['title'].lower() == available_mod['title'].lower():
                            try:
                                if self.is_update_available(installed_mod, available_mod):
                                    updates_available = True
                                    mods_to_update.append({
                                        'installed': installed_mod,
                                        'available': available_mod
                                    })
                            except Exception as e:
                                error_message = f"Error checking update for mod {installed_mod['title']}: {str(e)}"
                                self.set_status_safe(error_message)
                            break

                # If updates are available, show single prompt
                if mods_to_update:
                    update_message = "Updates available for the following mods:\n\n"
                    for mod in mods_to_update:
                        installed = mod['installed']
                        available = mod['available']
                        update_message += f"• {installed['title']}\n"
                        update_message += f"  Current version: {installed.get('version', 'Unknown')}\n"
                        update_message += f"  New version: {available.get('version', 'Unknown')}\n\n"
                    update_message += "Would you like to install all updates?"

                    if silent or messagebox.askyesno("Updates Available", update_message):
                        for mod in mods_to_update:
                            self.download_and_install_mod(mod['available'])

            # check for gdweave update
            gdweave_version = self.get_gdweave_version()
            if gdweave_version != self.settings.get('gdweave_version', 'Unknown'):
                updates_available = True
                if (
                    silent
                    or not silent
                    and messagebox.askyesno(
                        "Update Available",
                        "Update available for GDWeave. Do you want to update?",
                    )
                ):
                    self.install_gdweave()
                else:
                    self.set_status_safe("GDWeave update skipped by user.")

            if not silent and not program_updated and not updates_available:
                messagebox.showinfo("Up to Date", "Your mods, GDWeave, and HLS are up to date!")
                self.set_status_safe("No updates available.")
            elif not updates_available:
                self.set_status_safe("No updates available.")
        except Exception as e:
            error_message = f"Failed to check for updates: {str(e)}"
            self.set_status_safe(error_message)

    def is_update_available(self, installed_mod, available_mod):
        """Check if an update is available for a mod"""
        try:
            logging.info(f"Checking for updates - Installed mod: {installed_mod.get('title')}, Available mod: {available_mod.get('title')}")
            
            # get base thunderstore id by removing version component
            def get_base_id(thunderstore_id):
                if not thunderstore_id:
                    logging.debug(f"No thunderstore_id provided")
                    return ''
                # match version pattern at end of string
                version_pattern = r'-\d+\.\d+\.\d+$'
                base_id = re.sub(version_pattern, '', thunderstore_id)
                logging.debug(f"Converting thunderstore_id '{thunderstore_id}' to base_id '{base_id}'")
                return base_id
                
            installed_base_id = get_base_id(installed_mod.get('thunderstore_id', ''))
            available_base_id = get_base_id(available_mod.get('thunderstore_id', ''))
            
            logging.info(f"Comparing base IDs - Installed: {installed_base_id}, Available: {available_base_id}")
            
            # if no thunderstore ids or different mods, no update needed
            if not installed_base_id or not available_base_id or installed_base_id != available_base_id:
                logging.info("No update needed - Different or missing thunderstore IDs")
                return False
                
            def parse_version(version_str):
                logging.debug(f"Parsing version string: {version_str}")
                # extract version numbers, defaulting to 0.0.0
                match = re.search(r'(\d+)\.(\d+)\.(\d+)', version_str or '0.0.0')
                if not match:
                    logging.debug("No version match found, using default [0,0,0]")
                    return [0, 0, 0]
                version = [int(x) for x in match.groups()]
                logging.debug(f"Parsed version: {version}")
                return version
                
            installed_version = parse_version(installed_mod.get('version'))
            available_version = parse_version(available_mod.get('version'))
            
            logging.info(f"Comparing versions - Installed: {installed_version}, Available: {available_version}")
            
            # compare version components
            for i in range(3):
                if available_version[i] > installed_version[i]:
                    logging.info(f"Update available - Component {i} is newer ({available_version[i]} > {installed_version[i]})")
                    return True
                elif available_version[i] < installed_version[i]:
                    logging.info(f"No update needed - Component {i} is older ({available_version[i]} < {installed_version[i]})")
                    return False
            
            logging.info("No update needed - Versions are identical")
            return False
            
        except Exception as e:
            error_msg = f"Error checking update for mod {installed_mod.get('title')}: {str(e)}"
            logging.error(error_msg)
            logging.error(f"Full traceback: {traceback.format_exc()}")
            return False

    # saves the current state of installed mods to a cache file
    def save_mod_cache(self):
        try:
            mod_cache = {
                mod['id']: {
                    'title': mod['title'],
                    'version': mod.get('version', 'Unknown'),
                    'enabled': mod.get('enabled', True),
                    'third_party': mod.get('third_party', False),
                }
                for mod in self.installed_mods
            }
            with open(self.mod_cache_file, 'w') as f:
                json.dump(mod_cache, f, indent=2)
            logging.info(f"Mod cache saved. Total mods cached: {len(mod_cache)}")
        except Exception as e:
            error_message = f"Failed to save mod cache: {str(e)}"
            self.set_status(error_message)
            logging.info(error_message)
            
    # copies a mod from the app data directory to the game directory
    def copy_mod_to_game(self, mod_info):
        mod_id = mod_info['id']
        is_third_party = mod_info.get('third_party', False)
        
        if is_third_party:
            source_dir = os.path.join(self.mods_dir, "3rd_party", mod_id)
        else:
            source_dir = os.path.join(self.mods_dir, mod_id)
        
        logging.info(f"copy_mod_to_game called for mod '{mod_info['title']}' (ID: {mod_id}, Third Party: {is_third_party})")
        logging.info(f"Source directory: {source_dir}")

        if not os.path.exists(source_dir):
            logging.error(f"Source directory for mod '{mod_info['title']}' (ID: {mod_id}) not found.")
            return

        logging.info(f"Contents of source directory {source_dir} before copying:")
        for root, dirs, files in os.walk(source_dir):
            for file in files:
                logging.info(os.path.join(root, file))

        if not self.settings.get('game_path'):
            logging.error("Game path not set. Cannot copy mod to game.")
            return

        destination_dir = os.path.join(self.settings['game_path'], 'GDWeave', 'Mods', mod_id)
        logging.info(f"Destination directory: {destination_dir}")

        try:
            if os.path.exists(destination_dir):
                logging.info(f"Removing existing destination directory: {destination_dir}")
                shutil.rmtree(destination_dir)
            
            logging.info(f"Copying from {source_dir} to {destination_dir}")
            shutil.copytree(source_dir, destination_dir)
            
            logging.info(f"Contents of destination directory {destination_dir} after copying:")
            for root, dirs, files in os.walk(destination_dir):
                for file in files:
                    logging.info(os.path.join(root, file))
            
            logging.info(f"Mod '{mod_info['title']}' (ID: {mod_id}) copied successfully to game directory.")
        except Exception as e:
            logging.error(f"Error copying mod '{mod_info['title']}' (ID: {mod_id}) to game directory: {str(e)}")
            logging.error(traceback.format_exc())

    # removes a mod from the game directory
    def remove_mod_from_game(self, mod):
        gdweave_mods_path = os.path.join(self.settings['game_path'], 'GDWeave', 'Mods')
        mod_path_in_game = os.path.join(gdweave_mods_path, mod['id'])
        
        if os.path.exists(mod_path_in_game):
            logging.info(f"Removing mod from game: {mod_path_in_game}")
            shutil.rmtree(mod_path_in_game)
            logging.info(f"Successfully removed mod '{mod['title']}' (ID: {mod['id']}) from game directory.")
        else:
            logging.info(f"Mod '{mod['title']}' (ID: {mod['id']}) not found in game directory.")

    # periodically checks for updates in the background
    def periodic_update_check(self):
        while True:
            time.sleep(3600)  # check every hour
            if self.settings.get('auto_update', False):
                try:
                    self.check_for_updates(silent=True)
                except Exception as e:
                    logging.info(f"Error during mod updates check: {str(e)}")
                    self.set_status(f"Error checking for mod updates: {str(e)}")
                try:
                    self.check_for_program_updates(silent=False)
                except Exception as e:
                    logging.info(f"Error during program updates check: {str(e)}")
                    self.set_status(f"Error checking for program updates: {str(e)}")

    # logs the current settings
    def print_settings(self):
        logging.info("Current settings:")
        for key, value in self.settings.items():
            logging.info(f"  {key}: {value}")

    # opens a file dialog to select the game directory
    def browse_game_directory(self):
        if directory := filedialog.askdirectory():
            self.game_path_entry.delete(0, tk.END)
            self.game_path_entry.insert(0, directory)
            self.save_game_path()

    # saves the selected game path to settings
    def save_game_path(self):
        new_path = self.game_path_entry.get()
        if os.path.exists(new_path):
            self.settings['game_path'] = new_path
            self.save_settings()
            self.set_status(f"Game path updated to: {new_path}")
            logging.info(f"Game path updated to: {new_path}")
            self.update_setup_status()
        else:
            self.set_status("Invalid game path. Please enter a valid directory.")
            logging.info("Invalid game path entered.")

    def get_display_name(self, mod_title):
        return mod_title.replace('_', ' ')

    def get_backend_name(self, display_title):
        return display_title.replace(' ', '_')

    def handle_filter_toggle(self, filter_type):
        # save settings first
        self.save_settings()
        
        # store current category selection
        current_category = self.available_category.get()
        
        # clear the available mods list to force full refresh
        self.available_mods = []
        
        # reload available mods with new filter settings
        self.load_available_mods()
        
        # update category filters
        categories = {"All"}  # Always include "All" as an option
        for mod in self.available_mods:
            categories.update(mod.get('categories', []))
        
        # update combobox values while preserving selection if possible
        self.available_category['values'] = sorted(list(categories))
        
        # check if any mods in the current category exist after filtering
        mods_in_category = any(
            current_category in mod.get('categories', [])
            for mod in self.available_mods
        ) if current_category != "All" else True
        
        # keep current category if it exists and has mods, otherwise default to "All"
        if current_category in categories and mods_in_category:
            self.available_category.set(current_category)
        else:
            self.available_category.set("All")
        
        # apply filters
        self.filter_available_mods()

    # loads and displays available mods categorized
    def load_available_mods(self):
        try:
            # fetch mods from thunderstore api
            response = requests.get("https://thunderstore.io/c/webfishing/api/v1/package/")
            thunderstore_mods = response.json()
            
            # Track mods by name to detect duplicates
            mod_map = {}
            
            for mod in thunderstore_mods:
                is_deprecated = mod.get('is_deprecated', False)
                is_nsfw = mod.get('has_nsfw_content', False)
                
                # skip if mod should be filtered based on current settings
                if (is_deprecated and not self.show_deprecated.get()) or (is_nsfw and not self.show_nsfw.get()):
                    continue
                
                # get latest version info
                if not mod['versions']:
                    continue
                    
                latest_version = mod['versions'][0]
                
                # create mod info structure
                mod_info = {
                    'title': mod['name'],
                    'thunderstore_id': f"{mod['owner']}-{mod['name']}", 
                    'id': f"{mod['owner']}-{mod['name']}", 
                    'description': latest_version['description'],
                    'version': latest_version['version_number'],
                    'download': latest_version['download_url'],
                    'categories': mod['categories'],
                    'author': mod['owner'],
                    'dependencies': latest_version['dependencies'],
                    'website': latest_version.get('website_url', ''),
                    'downloads': latest_version.get('downloads', 0),
                    'likes': mod.get('rating_score', 0),
                    'last_updated': mod.get('date_updated', ''),
                    'is_deprecated': is_deprecated,
                    'has_nsfw_content': is_nsfw,
                    'date_updated': mod['date_updated']
                }
                
                # Handle duplicates
                if mod['name'] in mod_map:
                    existing = mod_map[mod['name']]
                    
                    # Keep non-deprecated version if available
                    if existing['is_deprecated'] and not is_deprecated:
                        mod_map[mod['name']] = mod_info
                    # If both non-deprecated or both deprecated, keep most recently updated
                    elif existing['is_deprecated'] == is_deprecated:
                        if mod['date_updated'] > existing['date_updated']:
                            mod_map[mod['name']] = mod_info
                else:
                    mod_map[mod['name']] = mod_info

            # Convert map to list
            self.available_mods = list(mod_map.values())
            
            # Collect unique categories
            categories = set()
            for mod in self.available_mods:
                categories.update(mod.get('categories', []))
            
            # Update category dropdown
            self.available_category['values'] = ["All"] + sorted(list(categories))
            self.available_category.set("All")
                
            # update the listbox with categorized mods
            self.update_available_mods_list()
            
        except requests.RequestException as e:
            self.set_status(f"Failed to load mods: {str(e)}")

    # checks if a mod id exists in the mods directory
    def mod_id_exists(self, mod_id):
        # check in the mods directory
        if os.path.exists(os.path.join(self.mods_dir, mod_id)):
            return True

        # check in the 3rd party mods directory
        if os.path.exists(os.path.join(self.mods_dir, "3rd_party", mod_id)):
            return True

        return any(mod.get('id') == mod_id for mod in self.installed_mods)

    # checks if a mod exists in the mods directory
    def mod_exists(self, mod):
        if mod.get('id') == 'separator':
            return True
        
        # if the mod doesn't have an 'id' we can't check if it exists
        if 'id' not in mod:
            return True  # assume it exists if we can't check
        
        if mod.get('third_party', False):
            mod_path = os.path.join(self.mods_dir, "3rd_party", mod['id'])
        else:
            mod_path = os.path.join(self.mods_dir, mod['id'])
        return os.path.exists(mod_path)

    # loads third-party mods from the mods directory
    def load_third_party_mods(self):
        third_party_mods_dir = os.path.join(self.mods_dir, "3rd_party")
        if not os.path.exists(third_party_mods_dir):
            return

        for mod_folder in os.listdir(third_party_mods_dir):
            mod_path = os.path.join(third_party_mods_dir, mod_folder)
            if os.path.isdir(mod_path):
                mod_info_path = os.path.join(mod_path, 'mod_info.json')
                if os.path.exists(mod_info_path):
                    with open(mod_info_path, 'r') as f:
                        mod_info = json.load(f)
                        mod_info['third_party'] = True
                        self.available_mods.append(mod_info)

if __name__ == "__main__":
    root = tk.Tk()
    app = HookLineSinkerUI(root)
    root.mainloop()