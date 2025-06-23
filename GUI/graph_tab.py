

###############
###  GRAPH  ###
###############

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import sqlite3
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

from constants import DARK_BG, ACCENT_COLOR, TEXT_COLOR, DARK_MEDIUM_BG, DB_FILE, PROFIT_COLOR, LOSS_COLOR
from parser import extract_txt_from_zip, parse_hand_history_file, insert_hand_details, parse_hero_contribution

class GraphTab(tk.Frame):
    def __init__(self, parent, main_app):
        tk.Frame.__init__(self, parent, bg=DARK_BG)
        self.main_app = main_app
        self.style = main_app.style  # Use the main app's style
        
        # Load saved rakeback percentage from database
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute("SELECT value FROM settings WHERE key = 'rakeback_percentage'")
        result = c.fetchone()
        conn.close()
        
        # Initialize rakeback variable with stored value or default to 0
        self.rakeback_var = tk.StringVar(value=result[0] if result else "0")
        
        self.create_graph_tab()

        
    def create_graph_tab(self):
        # Main container for the graph tab
        self.graph_container = tk.Frame(self, bg='#1a1a1a')  # Change background to match Range tab
        self.graph_container.pack(fill=tk.BOTH, expand=True)
        
        # Configure grid weights
        self.graph_container.grid_rowconfigure(0, weight=4)  # Top section gets 80%
        self.graph_container.grid_rowconfigure(1, weight=1)  # Bottom section gets 20%
        self.graph_container.grid_columnconfigure(0, weight=1)  # Left column
        self.graph_container.grid_columnconfigure(1, weight=4)  # Right column (wider)
        
        # Left panel (narrow column)
        left_panel = tk.Frame(self.graph_container, bd=2, relief=tk.GROOVE, bg='#1a1a1a')
        left_panel.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)
        
        # Configure left panel with two sections
        left_panel.grid_rowconfigure(0, weight=6)  # Stats section 60%
        left_panel.grid_rowconfigure(1, weight=4)  # Stakes section 40%
        left_panel.grid_columnconfigure(0, weight=1)
        
        # Stats section
        self.stats_section = tk.Frame(left_panel, bg='#1a1a1a', bd=2, relief=tk.GROOVE)
        self.stats_section.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)
        
        # Create a fixed-width label for stats to prevent resizing
        self.stats_label = tk.Label(
            self.stats_section,
            text="Total Profit: $0.00\nTotal Profit (BB): 0 BB\nBB/100: 0\nRake & Jackpot Paid: $0.00\nTotal Hands: 0",
            bg='#1a1a1a',
            fg='white',
            font=("Arial", 12),
            justify=tk.LEFT,
            width=30,  # Fixed width to prevent resizing
            anchor="nw"
        )
        self.stats_label.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Add a separator
        separator = tk.Frame(self.stats_section, height=1, bg='gray')
        separator.pack(fill=tk.X, padx=5, pady=5)
        
        # Add "Deduct Rake" checkbox at the bottom
        self.deduct_rake_var = tk.BooleanVar(value=False)
        
        # Create a frame to hold the checkbox and rakeback entry
        self.rake_frame = tk.Frame(self.stats_section, bg=DARK_BG)
        self.rake_frame.pack(fill=tk.X, padx=5, pady=5)
        
        self.deduct_rake_check = tk.Checkbutton(
            self.rake_frame,
            text="Deduct Rake",
            bg=DARK_BG,
            fg=TEXT_COLOR,
            selectcolor=DARK_BG,
            activebackground=DARK_BG,
            activeforeground=TEXT_COLOR,
            variable=self.deduct_rake_var,
            command=self.refresh_graph_tab,
            highlightthickness=0,
            highlightbackground=DARK_BG,
            highlightcolor=DARK_BG,
            takefocus=False
        )
        self.deduct_rake_check.pack(side=tk.LEFT, anchor=tk.W)
        
        # Add Rakeback % label and entry
        tk.Label(self.rake_frame, text="Rakeback %:", bg=DARK_BG, fg=TEXT_COLOR, takefocus=False).pack(side=tk.LEFT, padx=(10, 5))
        
        # Validate function to ensure only numbers and a single decimal point are entered
        def validate_rakeback(value):
            if value == "":
                return True
            try:
                # Allow for decimal input
                if value.count('.') <= 1:
                    # Check if it's a valid float between 0 and 100
                    val = float(value)
                    return 0 <= val <= 100
                return False
            except ValueError:
                return False
        
        # Register the validation command
        validate_cmd = self.register(validate_rakeback)
        
        # Create the entry widget with validation
        self.rakeback_entry = tk.Entry(
            self.rake_frame, 
            textvariable=self.rakeback_var, 
            width=5,
            validate="key", 
            validatecommand=(validate_cmd, '%P'),
            takefocus=False
        )
        self.rakeback_entry.pack(side=tk.LEFT)
        
        # Add % sign label
        tk.Label(self.rake_frame, text="%", bg=DARK_BG, fg=TEXT_COLOR).pack(side=tk.LEFT)
        
        # Function to save rakeback percentage
        def save_rakeback_percentage(event=None):
            try:
                rakeback_pct = self.rakeback_var.get()
                conn = sqlite3.connect(DB_FILE)
                c = conn.cursor()
                c.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", 
                         ('rakeback_percentage', rakeback_pct))
                print(f"Rakeback percentage saved: {rakeback_pct}")
                conn.commit()
                conn.close()
                self.refresh_graph_tab()
                self.update_adjusted_profit()
            except Exception as e:
                print(f"Error saving rakeback: {e}")
        
        # Bind the entry to update the graph when Enter is pressed or focus is lost
        self.rakeback_entry.bind("<Return>", save_rakeback_percentage)
        self.rakeback_entry.bind("<FocusOut>", save_rakeback_percentage)
        
        # Stakes section (in its own frame with border)
        self.stakes_section = tk.Frame(left_panel, bg='#1a1a1a', bd=2, relief=tk.GROOVE)
        self.stakes_section.grid(row=1, column=0, sticky="nsew", padx=5, pady=5)
        
        # Create stake buttons
        stakes = ['All']  # Will be populated with actual stakes
        self.stake_buttons = {}
        self.selected_stake = None  # Default to All Stakes selected
        
        # Create or update stake buttons
        # First, remove any existing buttons
        for widget in self.stakes_section.winfo_children():
            widget.destroy()
        
        # Create new buttons for each stake
        self.stake_buttons = {}
        for stake in stakes:
            btn = tk.Button(
                self.stakes_section,
                text=stake if stake != 'All' else 'All Stakes',
                bg='#00ace6' if stake == 'All' else '#1c1c1c',  # All Stakes is selected by default
                fg='white',
                font=("Arial", 10),
                command=lambda s=stake: self.filter_by_stake(s)
            )
            btn.pack(fill=tk.X, padx=5, pady=2)
            self.stake_buttons[stake] = btn

        # Graph panel (wide right column)
        self.fig = Figure(figsize=(6,4), dpi=100, facecolor='#1a1a1a')
        self.ax = self.fig.add_subplot(111)
        self.ax.set_facecolor('#1a1a1a')
        self.canvas = FigureCanvasTkAgg(self.fig, master=self.graph_container)
        self.canvas.get_tk_widget().grid(row=0, column=1, sticky="nsew", padx=5, pady=5)

        # Position panel (bottom spanning both columns)
        self.position_panel = tk.Frame(self.graph_container, bd=2, relief=tk.GROOVE, bg='#1a1a1a')
        self.position_panel.grid(row=1, column=0, columnspan=2, sticky="nsew", padx=5, pady=5)
        
        # Create position buttons in horizontal layout
        positions = ['All', 'BB', 'SB', 'BTN', 'CO', 'HJ', 'UTG']
        self.position_buttons = {}
        self.selected_position = None
        
        # Create a frame for the buttons
        button_frame = tk.Frame(self.position_panel, bg='#1a1a1a')
        button_frame.pack(expand=True, pady=20)
        
        for i, pos in enumerate(positions):
            btn = tk.Button(
                button_frame,
                text=f"{pos}\nWinloss: $0.00\nHands: 0",
                bg='#00ace6' if pos == 'All' else '#1c1c1c',  # Use new color for buttons
                fg='white',
                font=("Arial", 10),
                width=15,
                height=4,
                command=lambda p=pos: self.filter_by_position(p)
            )
            btn.grid(row=0, column=i, padx=5)
            self.position_buttons[pos] = btn
            
        # Initialize the graph with data
        self.refresh_graph_tab()
    

    def filter_by_position(self, position):
        """Filter graph data by selected position"""
        if position == 'All':
            self.selected_position = None
        else:
            if self.selected_position == position:
                self.selected_position = None  # Deselect if already selected
            else:
                self.selected_position = position
        
        # Update button appearances
        for pos, btn in self.position_buttons.items():
            if (pos == 'All' and self.selected_position is None) or pos == self.selected_position:
                btn.config(bg='#00ace6')  # Use new color for selected buttons
            else:
                btn.config(bg='#1c1c1c')  # Normal
            
        self.refresh_graph_tab()

    def filter_by_stake(self, stake):
        """Filter graph data by selected stake"""
        if stake == 'All':
            self.selected_stake = None
        else:
            if self.selected_stake == stake:
                self.selected_stake = None  # Deselect if already selected
            else:
                self.selected_stake = stake
        
        # Update button appearances
        for s, btn in self.stake_buttons.items():
            if (s == 'All' and self.selected_stake is None) or s == self.selected_stake:
                btn.config(bg='#00ace6')  # Use new color for selected buttons
            else:
                btn.config(bg='#1c1c1c')  # Normal
            
        self.refresh_graph_tab()

    def refresh_graph_tab(self):
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        
        # Get all unique stakes from the database
        c.execute("SELECT DISTINCT stake FROM hands ORDER BY stake")
        stakes = ['All'] + [row[0] for row in c.fetchall()]
        
        # Create or update stake buttons
        # First, remove any existing buttons
        for widget in self.stakes_section.winfo_children():
            widget.destroy()
        
        # Create new buttons for each stake
        self.stake_buttons = {}
        for stake in stakes:
            btn = tk.Button(
                self.stakes_section,
                text=stake if stake != 'All' else 'All Stakes',
                bg='#1c1c1c' if stake != self.selected_stake and not (stake == 'All' and self.selected_stake is None) else '#00ace6',
                fg='white',
                font=("Arial", 10),
                command=lambda s=stake: self.filter_by_stake(s)
            )
            btn.pack(fill=tk.X, padx=5, pady=2)
            self.stake_buttons[stake] = btn

        # Determine which profit column to use based on checkbox and rakeback
        if self.deduct_rake_var.get():
            # If deducting rake, use adjusted_profit which includes rakeback for winning hands
            profit_column = "adjusted_profit"
        else:
            # If not deducting rake, use hero_profit_with_rake (includes rake)
            profit_column = "hero_profit_with_rake"
        
        # Build query
        query = f"""
            SELECT 
                {profit_column} as profit,
                stake,
                hero_position,
                rake,
                jackpot,
                hero_profit
            FROM hands
            ORDER BY date_time
        """
        params = []
        
        # Apply stake filter if selected
        if self.selected_stake:
            query = f"""
                SELECT 
                    {profit_column} as profit,
                    stake,
                    hero_position,
                    rake,
                    jackpot,
                    hero_profit
                FROM hands
                WHERE stake = ?
                ORDER BY date_time
            """
            params = [self.selected_stake]
        
        # Apply position filter if selected
        if self.selected_position:
            if self.selected_stake:
                query = f"""
                    SELECT 
                        {profit_column} as profit,
                        stake,
                        hero_position,
                        rake,
                        jackpot,
                        hero_profit
                    FROM hands
                    WHERE stake = ? AND hero_position = ?
                    ORDER BY date_time
                """
                params = [self.selected_stake, self.selected_position]
            else:
                query = f"""
                    SELECT 
                        {profit_column} as profit,
                        stake,
                        hero_position,
                        rake,
                        jackpot,
                        hero_profit
                    FROM hands
                    WHERE hero_position = ?
                    ORDER BY date_time
                """
                params = [self.selected_position]
        
        c.execute(query, params)
        rows = c.fetchall()

        # Get rakeback percentage (convert from percentage to decimal)
        try:
            rakeback_pct = float(self.rakeback_var.get()) / 100.0
        except ValueError:
            rakeback_pct = 0.0
        
        # Ensure rakeback percentage is between 0 and 1
        rakeback_pct = max(0.0, min(1.0, rakeback_pct))
        
        # Calculate stats - now using the selected profit column directly
        total_profit = sum(row[0] for row in rows) if rows else 0
        total_hands = len(rows)
        
        # Calculate rake and jackpot totals - only for hands where Hero won
        # Always use hero_profit (not profit_with_rake) to determine winning hands
        total_rake = sum(row[3] for row in rows if row[5] > 0) if rows else 0
        total_jackpot = sum(row[4] for row in rows if row[5] > 0) if rows else 0
        total_rake_and_jackpot = total_rake + total_jackpot
        
        # Calculate BB stats
        if rows:
            # Convert stake strings like "$0.1/$0.2" to BB size (the larger number)
            stakes = [float(row[1].split('/')[-1].replace('$', '')) for row in rows]
            bb_profits = [row[0] / stake for row, stake in zip(rows, stakes)]
            total_bb = sum(bb_profits)
            bb_per_100 = (total_bb / total_hands) * 100 if total_hands > 0 else 0
        else:
            total_bb = 0
            bb_per_100 = 0

        # Update stats display in column format
        profit_type = "Profit (rake deducted)" if self.deduct_rake_var.get() else "Profit (with rake)"
        
        # Clear existing stats widgets
        for widget in self.stats_section.winfo_children():
            if widget != self.rake_frame:  # Keep the rake frame
                widget.destroy()
        
        # Create a frame for the stats with a grid layout
        stats_grid = tk.Frame(self.stats_section, bg=DARK_BG)
        stats_grid.pack(fill=tk.X, padx=5, pady=5, before=self.rake_frame)
        
        # Configure the grid columns
        stats_grid.columnconfigure(0, weight=1)  # Labels column
        stats_grid.columnconfigure(1, weight=1)  # Values column
        
        # Add stats rows
        row = 0
        
        # Total Profit
        tk.Label(stats_grid, text=f"Total {profit_type}:", bg=DARK_BG, fg=TEXT_COLOR, anchor='w').grid(row=row, column=0, sticky='w', padx=5, pady=2)
        tk.Label(stats_grid, text=f"${total_profit:,.2f}", bg=DARK_BG, fg=PROFIT_COLOR if total_profit >= 0 else LOSS_COLOR, anchor='e').grid(row=row, column=1, sticky='e', padx=5, pady=2)
        row += 1
        
        # Total Profit (BB)
        tk.Label(stats_grid, text="Total Profit (BB):", bg=DARK_BG, fg=TEXT_COLOR, anchor='w').grid(row=row, column=0, sticky='w', padx=5, pady=2)
        tk.Label(stats_grid, text=f"{total_bb:,.2f} BB", bg=DARK_BG, fg=PROFIT_COLOR if total_bb >= 0 else LOSS_COLOR, anchor='e').grid(row=row, column=1, sticky='e', padx=5, pady=2)
        row += 1
        
        # BB/100
        tk.Label(stats_grid, text="BB/100:", bg=DARK_BG, fg=TEXT_COLOR, anchor='w').grid(row=row, column=0, sticky='w', padx=5, pady=2)
        tk.Label(stats_grid, text=f"{bb_per_100:.2f}", bg=DARK_BG, fg=PROFIT_COLOR if bb_per_100 >= 0 else LOSS_COLOR, anchor='e').grid(row=row, column=1, sticky='e', padx=5, pady=2)
        row += 1
        
        # Rake & Jackpot Paid
        tk.Label(stats_grid, text="Rake & Jackpot Paid:", bg=DARK_BG, fg=TEXT_COLOR, anchor='w').grid(row=row, column=0, sticky='w', padx=5, pady=2)
        tk.Label(stats_grid, text=f"${total_rake_and_jackpot:,.2f}", bg=DARK_BG, fg=TEXT_COLOR, anchor='e').grid(row=row, column=1, sticky='e', padx=5, pady=2)
        row += 1
        
        # Total Hands
        tk.Label(stats_grid, text="Total Hands:", bg=DARK_BG, fg=TEXT_COLOR, anchor='w').grid(row=row, column=0, sticky='w', padx=5, pady=2)
        tk.Label(stats_grid, text=f"{total_hands:,}", bg=DARK_BG, fg=TEXT_COLOR, anchor='e').grid(row=row, column=1, sticky='e', padx=5, pady=2)
        row += 1
        
        # Calculate additional stats if we have hands
        if total_hands > 0:
            # VPIP (Voluntarily Put $ In Pot) - percentage of hands where hero put money in preflop
            # Exclude hands where hero only contributed 1SB in SB position or 1BB in BB position
            c.execute("""
                SELECT COUNT(*) FROM hands 
                WHERE (
                    (hero_position = 'SB' AND hero_contribution > CAST(SUBSTR(stake, INSTR(stake, '$') + 1, INSTR(stake, '/') - INSTR(stake, '$') - 1) AS REAL))
                    OR (hero_position = 'BB' AND hero_contribution > CAST(SUBSTR(stake, INSTR(stake, '/') + 2) AS REAL))
                    OR (hero_position NOT IN ('SB', 'BB') AND hero_contribution > 0)
                )
                AND (stake = ? OR ? IS NULL)
                AND (hero_position = ? OR ? IS NULL)
            """, (self.selected_stake, self.selected_stake, self.selected_position, self.selected_position))
            vpip_hands = c.fetchone()[0]
            vpip_percentage = (vpip_hands / total_hands) * 100 if total_hands > 0 else 0
            
            # PFR (Preflop Raise) - percentage of hands where hero raised preflop
            c.execute("""
                SELECT COUNT(*) FROM hands 
                WHERE preflop_scenario IN ('open (single raised)', '3bet', '4bet', '5bet+')
                AND (stake = ? OR ? IS NULL)
                AND (hero_position = ? OR ? IS NULL)
            """, (self.selected_stake, self.selected_stake, self.selected_position, self.selected_position))
            pfr_hands = c.fetchone()[0]
            pfr_percentage = (pfr_hands / total_hands) * 100 if total_hands > 0 else 0
            
            # 3bet% - percentage of hands where hero 3bet when had opportunity
            c.execute("""
                SELECT COUNT(*) FROM hands 
                WHERE preflop_scenario = '3bet'
                AND had_3bet_op = 1
                AND (stake = ? OR ? IS NULL)
                AND (hero_position = ? OR ? IS NULL)
            """, (self.selected_stake, self.selected_stake, self.selected_position, self.selected_position))
            threebet_hands = c.fetchone()[0]
            
            c.execute("""
                SELECT COUNT(*) FROM hands 
                WHERE had_3bet_op = 1
                AND (stake = ? OR ? IS NULL)
                AND (hero_position = ? OR ? IS NULL)
            """, (self.selected_stake, self.selected_stake, self.selected_position, self.selected_position))
            threebet_op_hands = c.fetchone()[0]
            threebet_percentage = (threebet_hands / threebet_op_hands) * 100 if threebet_op_hands > 0 else 0
            
            # 4bet% - percentage of hands where hero 4bet when had opportunity
            c.execute("""
                SELECT COUNT(*) FROM hands 
                WHERE preflop_scenario = '4bet'
                AND had_4bet_op = 1
                AND (stake = ? OR ? IS NULL)
                AND (hero_position = ? OR ? IS NULL)
            """, (self.selected_stake, self.selected_stake, self.selected_position, self.selected_position))
            fourbet_hands = c.fetchone()[0]
            
            c.execute("""
                SELECT COUNT(*) FROM hands 
                WHERE had_4bet_op = 1
                AND (stake = ? OR ? IS NULL)
                AND (hero_position = ? OR ? IS NULL)
            """, (self.selected_stake, self.selected_stake, self.selected_position, self.selected_position))
            fourbet_op_hands = c.fetchone()[0]
            fourbet_percentage = (fourbet_hands / fourbet_op_hands) * 100 if fourbet_op_hands > 0 else 0
            
            # WTSD (Went To ShowDown) - percentage of hands that went to showdown
            c.execute("""
                SELECT COUNT(*) FROM hands 
                WHERE river_action IS NOT NULL AND river_action != ''
                AND (stake = ? OR ? IS NULL)
                AND (hero_position = ? OR ? IS NULL)
            """, (self.selected_stake, self.selected_stake, self.selected_position, self.selected_position))
            wtsd_hands = c.fetchone()[0]
            wtsd_percentage = (wtsd_hands / total_hands) * 100 if total_hands > 0 else 0
            
            # W$SD (Won money at ShowDown) - percentage of showdowns where hero won money
            c.execute(f"""
                SELECT COUNT(*) FROM hands 
                WHERE river_action IS NOT NULL AND river_action != ''
                AND {profit_column} > 0
                AND (stake = ? OR ? IS NULL)
                AND (hero_position = ? OR ? IS NULL)
            """, (self.selected_stake, self.selected_stake, self.selected_position, self.selected_position))
            won_sd_hands = c.fetchone()[0]
            wsd_percentage = (won_sd_hands / wtsd_hands) * 100 if wtsd_hands > 0 else 0
            
            # Display the new stats
            # VPIP
            tk.Label(stats_grid, text="VPIP:", bg=DARK_BG, fg=TEXT_COLOR, anchor='w').grid(row=row, column=0, sticky='w', padx=5, pady=2)
            tk.Label(stats_grid, text=f"{vpip_percentage:.1f}%", bg=DARK_BG, fg=TEXT_COLOR, anchor='e').grid(row=row, column=1, sticky='e', padx=5, pady=2)
            row += 1
            
            # PFR
            tk.Label(stats_grid, text="PFR:", bg=DARK_BG, fg=TEXT_COLOR, anchor='w').grid(row=row, column=0, sticky='w', padx=5, pady=2)
            tk.Label(stats_grid, text=f"{pfr_percentage:.1f}%", bg=DARK_BG, fg=TEXT_COLOR, anchor='e').grid(row=row, column=1, sticky='e', padx=5, pady=2)
            row += 1
            
            # 3bet%
            tk.Label(stats_grid, text="3bet%:", bg=DARK_BG, fg=TEXT_COLOR, anchor='w').grid(row=row, column=0, sticky='w', padx=5, pady=2)
            tk.Label(stats_grid, text=f"{threebet_percentage:.1f}%", bg=DARK_BG, fg=TEXT_COLOR, anchor='e').grid(row=row, column=1, sticky='e', padx=5, pady=2)
            row += 1
            
            # 4bet%
            tk.Label(stats_grid, text="4bet%:", bg=DARK_BG, fg=TEXT_COLOR, anchor='w').grid(row=row, column=0, sticky='w', padx=5, pady=2)
            tk.Label(stats_grid, text=f"{fourbet_percentage:.1f}%", bg=DARK_BG, fg=TEXT_COLOR, anchor='e').grid(row=row, column=1, sticky='e', padx=5, pady=2)
            row += 1
            
            # WTSD%
            tk.Label(stats_grid, text="WTSD%:", bg=DARK_BG, fg=TEXT_COLOR, anchor='w').grid(row=row, column=0, sticky='w', padx=5, pady=2)
            tk.Label(stats_grid, text=f"{wtsd_percentage:.1f}%", bg=DARK_BG, fg=TEXT_COLOR, anchor='e').grid(row=row, column=1, sticky='e', padx=5, pady=2)
            row += 1
            
            # W$SD%
            tk.Label(stats_grid, text="W$SD%:", bg=DARK_BG, fg=TEXT_COLOR, anchor='w').grid(row=row, column=0, sticky='w', padx=5, pady=2)
            tk.Label(stats_grid, text=f"{wsd_percentage:.1f}%", bg=DARK_BG, fg=TEXT_COLOR, anchor='e').grid(row=row, column=1, sticky='e', padx=5, pady=2)
            row += 1
        
        # Add a separator
        separator = tk.Frame(self.stats_section, height=1, bg='gray')
        separator.pack(fill=tk.X, padx=5, pady=5, before=self.rake_frame)

        if not rows:
            self.ax.clear()
            self.ax.set_title("No Data", color='white')
            self.canvas.draw()
            return

        # Calculate cumulative profit
        cumulative = []
        total = 0.0
        for profit, _, _, _, _, _ in rows:
            total += profit
            cumulative.append(total)

        # Create x-axis values (hand numbers)
        x_vals = list(range(1, len(cumulative) + 1))

        # Clear and redraw with dark theme
        self.ax.clear()
        self.ax.grid(True, color='gray', alpha=0.3)
        
        # Determine line color based on final profit
        line_color = '#00ace6' if cumulative[-1] >= 0 else '#CC0000'  # Blue if positive/zero, Red if negative
        
        line, = self.ax.plot(x_vals, cumulative, linestyle='-', color=line_color, linewidth=2, marker='o', markersize=2)

        # Style the axes
        self.ax.set_xlabel("Hand Number (Chronological)", color='white')
        profit_label = "Cumulative Profit (rake deducted) ($)" if self.deduct_rake_var.get() else "Cumulative Profit (with rake) ($)"
        self.ax.set_ylabel(profit_label, color='white')
        title = "Hero's Cumulative Profit" if not self.selected_position else f"Hero's Cumulative Profit - {self.selected_position}"
        self.ax.set_title(title, color='white')
        self.ax.tick_params(colors='white')
        for spine in self.ax.spines.values():
            spine.set_color('white')
            
        # Move y-axis ticks to the right side
        self.ax.yaxis.tick_right()
        # But keep the y-axis label on the left
        self.ax.yaxis.set_label_position('left')

        # Update position button stats
        for position, btn in self.position_buttons.items():
            if position == 'All':
                c.execute(f"""
                    SELECT 
                        COALESCE(SUM({profit_column}), 0) as winloss,
                        COUNT(*) as total_hands
                    FROM hands
                """)
            else:
                c.execute(f"""
                    SELECT 
                        COALESCE(SUM({profit_column}), 0) as winloss,
                        COUNT(*) as total_hands
                    FROM hands 
                    WHERE hero_position = ?
                """, (position,))
            
            row = c.fetchone()
            winloss = row[0] if row else 0
            total_hands = row[1] if row else 0
                
            btn.config(text=f"{position}\nWinloss: ${winloss:.2f}\nHands: {total_hands}")

        conn.close()

        # Store data as class attributes
        self.x_vals = x_vals
        self.cumulative = cumulative

        def motion_hover(event):
            if event.inaxes != self.ax:
                # Remove any existing vertical line
                if hasattr(self, 'v_line') and self.v_line in self.ax.lines:
                    self.v_line.remove()
                # Remove annotations
                for artist in self.ax.texts:
                    if hasattr(artist, 'is_hover_annotation'):
                        artist.remove()
                self.canvas.draw_idle()
                return

            # Get nearest x value
            x_coord = int(round(event.xdata))
            if x_coord < 1 or x_coord > len(self.x_vals):
                return

            # Get corresponding y value
            y_coord = self.cumulative[x_coord - 1]

            # Remove old vertical line if it exists
            if hasattr(self, 'v_line') and self.v_line in self.ax.lines:
                self.v_line.remove()

            # Add new vertical line
            self.v_line = self.ax.axvline(x=x_coord, color='grey', linestyle=':', alpha=0.5)

            # Remove old annotation
            for artist in self.ax.texts:
                if hasattr(artist, 'is_hover_annotation'):
                    artist.remove()

            # Determine if we're close to the right edge of the graph
            # Get the figure width in data coordinates
            x_min, x_max = self.ax.get_xlim()
            # If we're in the right 20% of the graph, place annotation to the left
            x_offset = -60 if event.xdata > (x_max - (x_max - x_min) * 0.2) else 10
            
            # Create new annotation at cursor position
            annotation = self.ax.annotate(
                f'Hand: {x_coord:,}\nProfit: ${y_coord:.2f}',
                xy=(event.xdata, event.ydata),
                xytext=(x_offset, 10),
                textcoords='offset points',
                bbox=dict(
                    boxstyle='round,pad=0.5',
                    fc='black',
                    alpha=0.8,
                    ec='white'
                ),
                color='white'
            )
            annotation.is_hover_annotation = True

            # Use blit for faster rendering - only update the changed parts
            self.canvas.draw_idle()

        # Connect the hover event
        self.canvas.mpl_connect('motion_notify_event', motion_hover)

        # Set figure background
        self.fig.patch.set_facecolor('#1a1a1a')
        
        # Draw with tight layout
        self.fig.tight_layout()
        self.canvas.draw()

    def update_adjusted_profit(self):
        try:
            # Get rakeback percentage and convert to decimal
            rakeback_pct = float(self.rakeback_var.get()) / 100.0
        except ValueError:
            rakeback_pct = 0.0
            
        # Connect to database
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        
        # Update adjusted_profit for all hands
        if rakeback_pct > 0:
            # Add rakeback percentage of paid_rake to hero_profit for all hands
            c.execute("""
                UPDATE hands 
                SET adjusted_profit = hero_profit + (paid_rake * ?)
            """, (rakeback_pct,))
        else:
            # If no rakeback, adjusted_profit equals hero_profit
            c.execute("UPDATE hands SET adjusted_profit = hero_profit")
            
        conn.commit()
        conn.close()
        
        # Refresh the display to show updated values
        self.refresh_graph_tab()

    