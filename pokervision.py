import sqlite3
import tkinter as tk
from tkinter import ttk
import numpy as np
import matplotlib
matplotlib.use("TkAgg")
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import matplotlib.pyplot as plt
from constants import *
from parser import *
from utils import *
import tkinter.messagebox as messagebox
import json
from PIL import Image, ImageTk
import os
import ctypes

def init_database():    
    """Create the local SQLite DB with a 'hands' table if not present."""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    
    # Create table if it doesn't exist
    c.execute("""
        CREATE TABLE IF NOT EXISTS hands (
            hand_id TEXT PRIMARY KEY,
            stake TEXT,
            date_time TEXT,
            hero_position TEXT,
            hero_cards TEXT,
            preflop_action TEXT,
            preflop_all TEXT,
            flop_action TEXT,
            flop_all TEXT,
            turn_action TEXT,
            turn_all TEXT,
            river_action TEXT,
            river_all TEXT,
            board_flop TEXT,
            board_turn TEXT,
            board_river TEXT,
            total_pot REAL,
            rake REAL,
            jackpot REAL,
            hero_profit REAL,
            hero_profit_with_rake REAL,
            seats_info TEXT,
            imported_on TEXT,
            preflop_scenario TEXT,
            had_rfi_opportunity INTEGER,
            had_3bet_op INTEGER,
            had_4bet_op INTEGER,
            hero_contribution REAL,
            adjusted_profit REAL,
            paid_rake REAL
        )
    """)
    
    # Check if hero_profit_with_rake column exists, add it if not
    c.execute("PRAGMA table_info(hands)")
    columns = [info[1] for info in c.fetchall()]
    
    if "hero_profit_with_rake" not in columns:
        try:
            c.execute("ALTER TABLE hands ADD COLUMN hero_profit_with_rake REAL")
            
            # Update existing rows with calculated values (including both rake and jackpot)
            c.execute("UPDATE hands SET hero_profit_with_rake = hero_profit + rake + jackpot")
        except sqlite3.OperationalError:
            # Column might have been added in another process
            pass
    
    # Check if hero_contribution column exists, add it if not
    if "hero_contribution" not in columns:
        try:
            c.execute("ALTER TABLE hands ADD COLUMN hero_contribution REAL")
            
            # Initialize with 0 for existing rows
            c.execute("UPDATE hands SET hero_contribution = 0.0")
        except sqlite3.OperationalError:
            # Column might have been added in another process
            pass
    
    # Check if adjusted_profit column exists, add it if not
    if "adjusted_profit" not in columns:
        try:
            c.execute("ALTER TABLE hands ADD COLUMN adjusted_profit REAL")
            
            # Initialize with hero_profit for existing rows
            c.execute("UPDATE hands SET adjusted_profit = hero_profit")
        except sqlite3.OperationalError:
            # Column might have been added in another process
            pass
    
    # Create settings table if it doesn't exist
    c.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    """)
    
    conn.commit()
    conn.close()


def get_all_hands(limit=None):
    """Fetch hands from DB, with optional limit."""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    
    if limit:
        c.execute("""
            SELECT hand_id, date_time, stake, hero_position, hero_cards,
                   total_pot, rake, jackpot, ROUND(hero_profit, 2) as hero_profit,
                   ROUND(hero_profit_with_rake, 2) as hero_profit_with_rake
            FROM hands
            ORDER BY rowid DESC
            LIMIT ?
        """, (limit,))
    else:
        c.execute("""
            SELECT hand_id, date_time, stake, hero_position, hero_cards,
                   total_pot, rake, jackpot, ROUND(hero_profit, 2) as hero_profit,
                   ROUND(hero_profit_with_rake, 2) as hero_profit_with_rake
            FROM hands
            ORDER BY rowid DESC
        """)
    
    rows = c.fetchall()
    conn.close()
    return rows




def build_range_matrix(stats):
    """Build a 13x13 matrix of 3bet percentages from stats."""
    mat = np.full((13,13), np.nan)
    rank_to_idx = {rank:i for i,rank in enumerate(RANKS)}
    for key,(cnt, tb, pct) in stats.items():
        if len(key)==2:
            # pair e.g. 'AA','KK'
            i = rank_to_idx[key[0]]
            mat[i,i] = pct
        elif len(key)==3:
            # e.g. 'AKo','AKs'
            r1 = key[0]
            r2 = key[1]
            suited = (key[2]=='s')
            i = rank_to_idx[r2]
            j = rank_to_idx[r1]
            if r1==r2:
                # already handled by pair
                continue
            if suited:
                if i<j:
                    mat[i,j] = pct
                else:
                    mat[j,i] = pct
            else:
                if i>j:
                    mat[i,j] = pct
                else:
                    mat[j,i] = pct
    return mat

def save_hand_to_db(data):
    """Save a parsed hand to the SQLite database."""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    
    # Calculate had_3bet_op
    had_3bet_op = determine_3bet_opportunity(data['preflop_all'])
    
    # Use the scenario that was already parsed and stored in data
    scenario = data['preflop_scenario']
    
    # Get rakeback percentage from settings
    c.execute("SELECT value FROM settings WHERE key = 'rakeback_percentage'")
    result = c.fetchone()
    rakeback_pct = float(result[0]) / 100.0 if result else 0.0
    
    # Calculate adjusted profit - only add rakeback for hands where hero won (GGPoker model)
    if data['hero_profit'] > 0:
        if rakeback_pct == 1.0:  # 100% rakeback
            adjusted_profit = data['hero_profit_with_rake']
        else:
            adjusted_profit = data['hero_profit'] + (data['rake'] * rakeback_pct)
    else:
        adjusted_profit = data['hero_profit']
    
    try:
        c.execute("""
            INSERT OR REPLACE INTO hands (
                hand_id, stake, date_time, hero_position, hero_cards,
                preflop_action, preflop_all, flop_action, flop_all,
                turn_action, turn_all, river_action, river_all,
                board_flop, board_turn, board_river,
                total_pot, rake, jackpot, hero_profit, hero_profit_with_rake,
                seats_info, imported_on, preflop_scenario,
                had_rfi_opportunity, had_3bet_op, had_4bet_op, hero_contribution,
                adjusted_profit, paid_rake
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            data['hand_id'], data['stake'], data['date_time'],
            data['hero_position'], data['hero_cards'],
            data['preflop_action'], data['preflop_all'],
            data['flop_action'], data['flop_all'],
            data['turn_action'], data['turn_all'],
            data['river_action'], data['river_all'],
            data['board_flop'], data['board_turn'], data['board_river'],
            data['total_pot'], data['rake'], data['jackpot'],
            data['hero_profit'], data['hero_profit_with_rake'],
            data['seats_info'],
            data['imported_on'],
            data['preflop_scenario'],
            data['had_rfi_opportunity'],
            data['had_3bet_op'],
            data['had_4bet_op'],
            data['hero_contribution'],
            data['adjusted_profit'],
            data['paid_rake']
        ))
        
        conn.commit()
        
    finally:
        conn.close()

from GUI.import_tab import ImportTab
from GUI.graph_tab import GraphTab
from GUI.range_tab import RangeTab
from GUI.leakhelper_tab import LeakHelperTab
from GUI.hand_details import HandDetails

class APIKeyDialog(tk.Toplevel):
    def __init__(self, parent, callback):
        super().__init__(parent)
        self.callback = callback
        self.title("Set API Key")
        self.geometry("400x200")
        self.resizable(False, False)
        
        # Model selection
        model_frame = tk.Frame(self)
        model_frame.pack(pady=10)
        
        tk.Label(model_frame, text="Select Model:").pack(side=tk.LEFT, padx=5)
        self.model_var = tk.StringVar(value="Gemini 2.0 Flash")
        model_dropdown = ttk.Combobox(
            model_frame, 
            textvariable=self.model_var,
            values=["Gemini 2.0 Flash", "Gemini 2.5 Pro"],
            state="readonly",
            width=20
        )
        model_dropdown.pack(side=tk.LEFT)
        
        # API Key entry
        tk.Label(self, text="Enter your API Key:").pack(pady=(10,5))
        self.api_key_entry = tk.Entry(self, width=50)
        self.api_key_entry.pack(pady=5)
        
        # Try to load existing settings
        try:
            with open('api_settings.json', 'r') as f:
                settings = json.loads(f.read())
                if settings.get('api_key'):
                    self.api_key_entry.insert(0, settings['api_key'])
                if settings.get('model'):
                    self.model_var.set(settings['model'])
        except (FileNotFoundError, json.JSONDecodeError):
            pass
        
        # Save button
        tk.Button(self, text="Save", command=self.save_api_key).pack(pady=10)
        
    def save_api_key(self):
        api_key = self.api_key_entry.get().strip()
        model = self.model_var.get()
        
        if api_key:
            # Save to file
            settings = {
                'api_key': api_key,
                'model': model
            }
            with open('api_settings.json', 'w') as f:
                json.dump(settings, f)
            
            # Call the callback with the new settings
            self.callback(api_key, model)
            self.destroy()
        else:
            messagebox.showerror("Error", "Please enter an API key")

class PokerTrackerApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("PokerVision")
        self.geometry("1300x800")
        
        # Set window icon and taskbar icon
        try:
            # Set window icon
            icon_path = os.path.join("Images", "Logo.png")
            icon_image = Image.open(icon_path)
            icon_photo = ImageTk.PhotoImage(icon_image)
            self.iconphoto(True, icon_photo)
            
            # Set taskbar icon (Windows specific)
            taskbar_icon_path = os.path.join("Images", "Icon.png")
            if os.name == 'nt':  # Windows
                myappid = 'poker.vision.app.1.0'  # arbitrary string
                ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
        except Exception as e:
            print(f"Error setting icons: {e}")
        
        # Define theme colors using global constants
        self.colors = {
            'bg_dark': DARK_BG,             # Main background
            'bg_medium': MEDIUM_BG,         # Panel background
            'bg_light': LIGHT_BG,           # Element background
            'accent': ACCENT_COLOR,         # Accent color for selected items
            'text': TEXT_COLOR,             # Main text color
            'text_secondary': TEXT_SECONDARY_COLOR,  # Secondary text color
            'border': BORDER_COLOR,         # Border color
            'positive': PROFIT_COLOR,       # Positive values (green)
            'negative': LOSS_COLOR,         # Negative values (red)
            'grid_line': GRID_COLOR         # Grid lines
        }
        
        # Configure the window
        self.configure(bg=self.colors['bg_dark'])
        
        # Initialize selection variables
        self.selected_stake = None
        self.selected_position = None
        
        # Initialize database first
        init_database()
        
        # Load rakeback percentage from settings
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute("SELECT value FROM settings WHERE key = 'rakeback_percentage'")
        result = c.fetchone()
        conn.close()
        
        # Initialize rakeback variable with stored value or default to 0
        self.rakeback_var = tk.StringVar(value=result[0] if result else "0")
        
        # Create a single style instance for the application
        self.style = ttk.Style()
        self.style.theme_use('default')
        
        # Configure the notebook style
        self.style.configure('TNotebook', background=self.colors['bg_dark'])
        self.style.configure('TNotebook.Tab', background=self.colors['bg_medium'], 
                        foreground=self.colors['text'], padding=[10, 5],
                        font=('Arial', 10, 'bold'))
        self.style.map('TNotebook.Tab', background=[('selected', self.colors['accent'])],
                 foreground=[('selected', self.colors['text'])])
        
        # Configure Treeview style
        self.style.configure("Treeview", 
                        background=self.colors['bg_light'], 
                        foreground=self.colors['text'], 
                        fieldbackground=self.colors['bg_light'],
                        rowheight=25)
        self.style.configure("Treeview.Heading", 
                        background=self.colors['bg_medium'], 
                        foreground=self.colors['text'],
                        font=('Arial', 9, 'bold'))
        self.style.map('Treeview', background=[('selected', self.colors['accent'])])
        
        # Create the notebook
        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill=tk.BOTH, expand=True)

        # Create menu bar
        self.menu_bar = tk.Menu(self)
        self.config(menu=self.menu_bar)
        
        # Create Tools menu
        tools_menu = tk.Menu(self.menu_bar, tearoff=0)
        self.menu_bar.add_cascade(label="Tools", menu=tools_menu)
        tools_menu.add_command(label="Configure AI Model", command=self.show_api_key_dialog)

        # Import Tab
        self.import_tab = ImportTab(self.notebook, self)
        self.notebook.add(self.import_tab, text="Import / Hands")

        # Graph Tab
        self.graph_tab = GraphTab(self.notebook, self)
        self.notebook.add(self.graph_tab, text="Graph")

        # Range Tab
        self.range_tab = RangeTab(self.notebook, self)
        self.notebook.add(self.range_tab, text="Range")
        
        # LeakHelper Tab
        self.leak_tab = LeakHelperTab(self.notebook, self)
        self.notebook.add(self.leak_tab, text="LeakHelper")

    def refresh_all_tabs(self):
        """Refresh all tabs in the application."""
        self.import_tab.refresh_import_tab()
        self.graph_tab.refresh_graph_tab()
        self.range_tab.refresh_range_tab()
        self.leak_tab.update_leak_display()

    def show_api_key_dialog(self):
        APIKeyDialog(self, self.update_api_key)
    
    def update_api_key(self, api_key, model):
        # Update the API key in HandDetails
        HandDetails.set_api_settings(api_key, model)
        messagebox.showinfo("Success", "API settings have been saved successfully!")

if __name__ == "__main__":
    init_database()
    app = PokerTrackerApp()
    app.mainloop()
        
