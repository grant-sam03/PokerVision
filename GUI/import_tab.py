########################
###  IMPORT / HANDS  ###
########################

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import sqlite3
import os
from datetime import datetime

from constants import DARK_BG, ACCENT_COLOR, TEXT_COLOR, DARK_MEDIUM_BG, DB_FILE
from parser import extract_txt_from_zip, parse_hand_history_file, insert_hand_details, parse_hero_contribution
from GUI.hand_details import HandDetails

class ImportTab(tk.Frame):
    def __init__(self, parent, main_app):
        tk.Frame.__init__(self, parent, bg=DARK_BG)
        self.main_app = main_app
        self.style = main_app.style  # Use the main app's style
        self.create_import_tab()
        
    def create_import_tab(self):
        # Create Import Frame
        self.import_frame = tk.Frame(self, bg=DARK_BG)
        self.import_frame.pack(fill=tk.BOTH, expand=True)

        # Set the background color of the import frame
        self.import_frame.configure(bg=DARK_BG)
        
        top_frame = tk.Frame(self.import_frame, bg=DARK_BG)
        top_frame.pack(side=tk.TOP, fill=tk.X, padx=5, pady=5)
        
        # Add buttons with the new color scheme
        self.import_button = tk.Button(
            top_frame, 
            text="Import Hand Histories", 
            command=self.import_files,
            bg=ACCENT_COLOR,
            fg=TEXT_COLOR
        )
        self.import_button.pack(side=tk.LEFT, padx=5)
        
        self.refresh_button = tk.Button(
            top_frame, 
            text="Refresh", 
            command=self.refresh_import_tab,
            bg=ACCENT_COLOR,
            fg=TEXT_COLOR
        )
        self.refresh_button.pack(side=tk.LEFT, padx=5)
        
        self.clear_button = tk.Button(
            top_frame, 
            text="Clear All Hands", 
            command=self.clear_hands,
            bg=ACCENT_COLOR,
            fg=TEXT_COLOR
        )
        self.clear_button.pack(side=tk.LEFT, padx=5)
        
        # Add sorting options
        sort_frame = tk.Frame(top_frame, bg='#1a1a1a')
        sort_frame.pack(side=tk.LEFT, padx=20)
        
        tk.Label(sort_frame, text="Sort by:", bg='#1a1a1a', fg='white').pack(side=tk.LEFT, padx=5)
        
        self.sort_options = ttk.Combobox(sort_frame, values=[
            "None",
            "Date (newest first)", 
            "Date (oldest first)",
            "Profit (highest first)", 
            "Profit (lowest first)",
            "Position",
            "Stake"
        ])
        self.sort_options.current(0)
        self.sort_options.pack(side=tk.LEFT, padx=5)
        
        self.apply_sort_button = tk.Button(
            sort_frame, 
            text="Apply Sort", 
            command=self.apply_sort,
            bg=ACCENT_COLOR,
            fg=TEXT_COLOR
        )
        self.apply_sort_button.pack(side=tk.LEFT, padx=5)
        
        # Add filter options
        filter_frame = tk.Frame(top_frame, bg=DARK_BG)
        filter_frame.pack(side=tk.LEFT, padx=20)
        
        tk.Label(filter_frame, text="Filter:", bg=DARK_BG, fg=TEXT_COLOR).pack(side=tk.LEFT, padx=5)
        
        self.filter_options = ttk.Combobox(filter_frame, values=[
            "None",
            "Position",
            "Stake",
            "Date Range",
            "Profit Range"
        ])
        self.filter_options.current(0)
        self.filter_options.pack(side=tk.LEFT, padx=5)
        
        self.filter_value = tk.Entry(filter_frame, width=15)
        self.filter_value.pack(side=tk.LEFT, padx=5)
        
        self.apply_filter_button = tk.Button(
            filter_frame, 
            text="Apply Filter", 
            command=self.apply_hand_filters,
            bg=ACCENT_COLOR,
            fg=TEXT_COLOR
        )
        self.apply_filter_button.pack(side=tk.LEFT, padx=5)
        
        self.clear_filter_button = tk.Button(
            filter_frame, 
            text="Clear Filters", 
            command=self.clear_hand_filters,
            bg=ACCENT_COLOR,
            fg=TEXT_COLOR
        )
        self.clear_filter_button.pack(side=tk.LEFT, padx=5)
        
        # Create treeview for hands
        self.tree_frame = tk.Frame(self.import_frame, bg=DARK_BG)
        self.tree_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Configure the style for the treeview
        self.style.configure("Treeview", 
                        background=DARK_MEDIUM_BG, 
                        foreground=TEXT_COLOR, 
                        fieldbackground=DARK_MEDIUM_BG,
                        rowheight=25)
        self.style.configure("Treeview.Heading", 
                        background=DARK_BG, 
                        foreground=TEXT_COLOR)
        self.style.map('Treeview', background=[('selected', ACCENT_COLOR)])
        
        # Create scrollbars
        vsb = ttk.Scrollbar(self.tree_frame, orient="vertical")
        hsb = ttk.Scrollbar(self.tree_frame, orient="horizontal")
        
        # Create the treeview with updated columns
        self.tree = ttk.Treeview(self.tree_frame, columns=("date", "hand_id", "stake", "position", "cards", "profit"), 
                                    show="headings", yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        
        # Configure scrollbars
        vsb.configure(command=self.tree.yview)
        hsb.configure(command=self.tree.xview)
        
        # Place scrollbars
        vsb.pack(side=tk.RIGHT, fill=tk.Y)
        hsb.pack(side=tk.BOTTOM, fill=tk.X)
        
        # Place treeview
        self.tree.pack(fill=tk.BOTH, expand=True)
        
        # Configure columns
        self.tree.heading("date", text="Date", command=lambda: self.sort_by_column("date"))
        self.tree.heading("hand_id", text="Hand ID", command=lambda: self.sort_by_column("hand_id"))
        self.tree.heading("position", text="Position", command=lambda: self.sort_by_column("position"))
        self.tree.heading("stake", text="Stake", command=lambda: self.sort_by_column("stake"))
        self.tree.heading("cards", text="Cards")
        self.tree.heading("profit", text="Profit", command=lambda: self.sort_by_column("profit"))
        
        self.tree.column("date", width=150, anchor=tk.W)
        self.tree.column("hand_id", width=100, anchor=tk.W)
        self.tree.column("position", width=80, anchor=tk.CENTER)
        self.tree.column("stake", width=80, anchor=tk.CENTER)
        self.tree.column("cards", width=100, anchor=tk.CENTER)
        self.tree.column("profit", width=100, anchor=tk.E)
        
        # Bind double-click event
        self.tree.bind("<Double-1>", self.on_row_double_click)
        
        # Status bar
        self.status_bar = tk.Label(
            self.import_frame, 
            text="Ready", 
            bd=1, 
            relief=tk.SUNKEN, 
            anchor=tk.W,
            bg='#1a1a1a',
            fg='white'
        )
        self.status_bar.pack(side=tk.BOTTOM, fill=tk.X)
        
        # Populate the treeview
        self.refresh_import_tab()

    def apply_hand_filters(self):
        """Apply the selected filters to the hand history display."""
        cards = [self.cards_filter.get(idx) for idx in self.cards_filter.curselection()]
        position = self.position_filter.get()
        opportunity = self.opportunity_filter.get()
        
        # Clear current display
        for row in self.tree.get_children():
            self.tree.delete(row)
        
        # Build query
        query = """
            SELECT hand_id, date_time, stake, hero_position, hero_cards,
                   total_pot, rake, jackpot, ROUND(hero_profit, 2) as hero_profit,
                   ROUND(hero_profit_with_rake, 2) as hero_profit_with_rake
            FROM hands
            WHERE 1=1
        """
        params = []
        
        # Add card filter
        if cards:
            card_conditions = []
            for hand in cards:
                if len(hand) == 2:  # Pair
                    # For pairs like "AA", match any two aces
                    rank = hand[0]
                    # Need to find two of the same rank in the hand
                    card_conditions.append("""
                        (hero_cards LIKE ? AND 
                         (
                            (substr(hero_cards, 1, 1) = ? AND substr(hero_cards, 4, 1) = ?) OR
                            (substr(hero_cards, 1, 1) = ? AND substr(hero_cards, 4, 1) = ?)
                         )
                        )
                    """)
                    params.extend([f"%{rank}%", rank, rank, rank, rank])
                elif len(hand) == 3:  # Suited or offsuit
                    rank1, rank2 = hand[0], hand[1]
                    suited = hand.endswith('s')
                    
                    if suited:
                        # For suited hands like "AKs", both cards must have the same suit
                        card_conditions.append("""
                            (hero_cards LIKE ? AND hero_cards LIKE ? AND 
                             substr(hero_cards, 2, 1) = substr(hero_cards, 5, 1))
                        """)
                        params.extend([f"%{rank1}%", f"%{rank2}%"])
                    else:  # offsuit
                        # For offsuit hands like "AKo", cards must have different suits
                        card_conditions.append("""
                            (hero_cards LIKE ? AND hero_cards LIKE ? AND 
                             substr(hero_cards, 2, 1) != substr(hero_cards, 5, 1))
                        """)
                        params.extend([f"%{rank1}%", f"%{rank2}%"])
            
            if card_conditions:
                query += " AND (" + " OR ".join(card_conditions) + ")"
        
        # Add position filter
        if position != 'All':
            query += " AND hero_position = ?"
            params.append(position)
        
        # Add opportunity filter
        if opportunity != 'All':
            if opportunity == 'RFI':
                query += " AND had_rfi_opportunity = 1"
            elif opportunity == '3-Bet':
                query += " AND had_3bet_op = 1"
            elif opportunity == '4-Bet':
                query += " AND had_4bet_op = 1"
        
        # Execute query and update display
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute(query, params)
        rows = c.fetchall()
        
        c.execute("SELECT hand_id, hero_cards FROM hands LIMIT 10")
        sample_cards = c.fetchall()
        
        conn.close()
        
        for row in rows:
            self.tree.insert("", tk.END, values=row)
        
        # Update status
        status_text = f"Showing {len(rows)} hands"
        if cards or position != 'All' or opportunity != 'All':
            status_text += " (filtered)"
        self.range_stats_label.config(text=status_text)

    def clear_hand_filters(self):
        """Clear all hand filters and show all hands."""
        self.cards_filter.selection_clear(0, tk.END)
        self.position_filter.set('All')
        self.opportunity_filter.set('All')
        self.refresh_import_tab()


    def sort_by_column(self, column):
        """Sort the treeview by a specific column."""
        # Get all items in the treeview
        items = [(self.tree.set(k, column), k) for k in self.tree.get_children('')]
        
        # Check if we're reversing the sort
        reverse = False
        if self.tree.heading(column, 'text').endswith('↑'):
            reverse = True
        
        # Sort based on column type
        if column == "profit":
            # Convert to float for numeric sorting
            items.sort(key=lambda x: float(x[0]) if x[0] else 0, reverse=reverse)
        else:
            # Regular string sorting
            items.sort(reverse=reverse)
        
        # Rearrange items in sorted positions
        for index, (_, item) in enumerate(items):
            self.tree.move(item, '', index)
        
        # Update the headings to show the sort arrow
        for col in self.tree['columns']:
            if col == column:
                # Get the original heading text without arrows
                heading_text = self.tree.heading(col, 'text')
                if '↑' in heading_text or '↓' in heading_text:
                    heading_text = heading_text.rstrip('↑↓')
                self.tree.heading(col, text=f"{heading_text} {'↓' if reverse else '↑'}")
            else:
                # Reset other column headings
                heading_text = self.tree.heading(col, 'text')
                if '↑' in heading_text or '↓' in heading_text:
                    heading_text = heading_text.rstrip('↑↓')
                self.tree.heading(col, text=heading_text)


    def refresh_import_tab_no_sort(self):
        """Refresh the import tab without applying any sort."""
        for row in self.tree.get_children():
            self.tree.delete(row)
        
        # Get all hands with default ordering
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        
        # Fetch only the required columns
        c.execute("""
            SELECT hand_id, date_time, stake, hero_position, hero_cards, ROUND(hero_profit, 2) as hero_profit
            FROM hands
            ORDER BY rowid DESC
        """)
        
        rows = c.fetchall()
        conn.close()
        
        for r in rows:
            # Format the date to show date and time on a single line
            date_parts = r[1].split() if len(r) > 1 and r[1] else ["", ""]
            formatted_date = f"{date_parts[0]} {date_parts[1] if len(date_parts) > 1 else ''}"
            
            # Create a new row with the formatted date
            formatted_row = (formatted_date,) + r[0:1] + r[2:5] + r[5:]
            self.tree.insert("", tk.END, values=formatted_row)

    def create_hand_details_frame(self, parent, hand_data):
        """Create a frame with detailed information about a hand."""
        # Create a frame with a dark background
        details_frame = tk.Frame(parent, bg='black', padx=10, pady=10)
        details_frame.pack(fill=tk.BOTH, expand=True)
        
        # Create a canvas with scrollbar for the content
        canvas = tk.Canvas(details_frame, bg='black', highlightthickness=0)
        scrollbar = ttk.Scrollbar(details_frame, orient="vertical", command=canvas.yview)
        scrollable_frame = tk.Frame(canvas, bg='black')
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        # Hand ID and Date
        header_frame = tk.Frame(scrollable_frame, bg='black')
        header_frame.pack(fill=tk.X, pady=(0, 10))
        
        hand_id_label = tk.Label(
            header_frame, 
            text=f"Hand ID: {hand_data['hand_id']}", 
            font=("Arial", 12, "bold"),
            fg='white',
            bg='black'
        )
        hand_id_label.pack(side=tk.LEFT)
        
        date_label = tk.Label(
            header_frame, 
            text=f"Date: {hand_data['date_time']}", 
            font=("Arial", 12),
            fg='white',
            bg='black'
        )
        date_label.pack(side=tk.RIGHT)
        
        # Basic info section
        basic_info_frame = tk.Frame(scrollable_frame, bg='#1c1c1c', padx=10, pady=10)
        basic_info_frame.pack(fill=tk.X, pady=(0, 10))
        
        # Row 1: Stake, Position, Cards
        row1 = tk.Frame(basic_info_frame, bg='#1c1c1c')
        row1.pack(fill=tk.X, pady=5)
        
        stake_label = tk.Label(
            row1, 
            text=f"Stake: {hand_data['stake']}", 
            font=("Arial", 11),
            fg='white',
            bg='#1c1c1c',
            width=20,
            anchor='w'
        )
        stake_label.pack(side=tk.LEFT)
        
        position_label = tk.Label(
            row1, 
            text=f"Position: {hand_data['hero_position']}", 
            font=("Arial", 11),
            fg='white',
            bg='#1c1c1c',
            width=20,
            anchor='w'
        )
        position_label.pack(side=tk.LEFT)
        
        cards_label = tk.Label(
            row1, 
            text=f"Cards: {hand_data['hero_cards']}", 
            font=("Arial", 11),
            fg='white',
            bg='#1c1c1c',
            width=20,
            anchor='w'
        )
        cards_label.pack(side=tk.LEFT)
        
        # Row 2: Board
        row2 = tk.Frame(basic_info_frame, bg='#1c1c1c')
        row2.pack(fill=tk.X, pady=5)
        
        board_text = ""
        if hand_data['board_flop']:
            board_text += f"Flop: {hand_data['board_flop']}"
        if hand_data['board_turn']:
            board_text += f" | Turn: {hand_data['board_turn']}"
        if hand_data['board_river']:
            board_text += f" | River: {hand_data['board_river']}"
        
        board_label = tk.Label(
            row2, 
            text=f"Board: {board_text}" if board_text else "Board: -", 
            font=("Arial", 11),
            fg='white',
            bg='#1c1c1c',
            anchor='w'
        )
        board_label.pack(fill=tk.X)
        
        # Row 3: Pot, Rake, Jackpot, Profit
        row3 = tk.Frame(basic_info_frame, bg='#1c1c1c')
        row3.pack(fill=tk.X, pady=5)
        
        pot_label = tk.Label(
            row3, 
            text=f"Total Pot: ${hand_data['total_pot']:.2f}", 
            font=("Arial", 11),
            fg='white',
            bg='#1c1c1c',
            width=15,
            anchor='w'
        )
        pot_label.pack(side=tk.LEFT)
        
        rake_label = tk.Label(
            row3, 
            text=f"Rake: ${hand_data['rake']:.2f}", 
            font=("Arial", 11),
            fg='white',
            bg='#1c1c1c',
            width=15,
            anchor='w'
        )
        rake_label.pack(side=tk.LEFT)
        
        jackpot_label = tk.Label(
            row3, 
            text=f"Jackpot: ${hand_data['jackpot']:.2f}", 
            font=("Arial", 11),
            fg='white',
            bg='#1c1c1c',
            width=15,
            anchor='w'
        )
        jackpot_label.pack(side=tk.LEFT)
        
        profit_color = '#00ace6' if hand_data['hero_profit'] > 0 else 'red' if hand_data['hero_profit'] < 0 else 'white'
        profit_label = tk.Label(
            row3, 
            text=f"Profit: ${hand_data['hero_profit']:.2f}", 
            font=("Arial", 11),
            fg=profit_color,
            bg='#1c1c1c',
            width=15,
            anchor='w'
        )
        profit_label.pack(side=tk.LEFT)
        
        # Row 4: Hero Contribution and Profit with Rake
        row4 = tk.Frame(basic_info_frame, bg='#1c1c1c')
        row4.pack(fill=tk.X, pady=5)
        
        # Calculate hero's contribution
        hero_contribution = parse_hero_contribution(hand_data['preflop_all'] + hand_data['flop_all'] + 
                                                   hand_data['turn_all'] + hand_data['river_all'], 
                                                   hand_data['hero_position'], hand_data['stake'])
        
        contribution_label = tk.Label(
            row4, 
            text=f"Hero Contribution: ${hero_contribution:.2f}", 
            font=("Arial", 11),
            fg='white',
            bg='#1c1c1c',
            width=30,
            anchor='w'
        )
        contribution_label.pack(side=tk.LEFT)
        
        profit_with_rake_color = '#00ace6' if hand_data['hero_profit_with_rake'] > 0 else 'red' if hand_data['hero_profit_with_rake'] < 0 else 'white'
        profit_with_rake_label = tk.Label(
            row4, 
            text=f"Profit with Rake: ${hand_data['hero_profit_with_rake']:.2f}", 
            font=("Arial", 11),
            fg=profit_with_rake_color,
            bg='#1c1c1c',
            width=30,
            anchor='w'
        )
        profit_with_rake_label.pack(side=tk.LEFT)
        
        # Row 5: Preflop Scenario and Opportunities
        row5 = tk.Frame(basic_info_frame, bg='#1c1c1c')
        row5.pack(fill=tk.X, pady=5)
        
        scenario_label = tk.Label(
            row5, 
            text=f"Preflop Scenario: {hand_data['preflop_scenario']}", 
            font=("Arial", 11),
            fg='white',
            bg='#1c1c1c',
            width=30,
            anchor='w'
        )
        scenario_label.pack(side=tk.LEFT)
        
        opportunities_text = []
        if hand_data['had_rfi_opportunity'] == 1:
            opportunities_text.append("RFI")
        if hand_data['had_3bet_op'] == 1:
            opportunities_text.append("3-Bet")
        if hand_data['had_4bet_op'] == 1:
            opportunities_text.append("4-Bet")
        
        opportunities_label = tk.Label(
            row5, 
            text=f"Opportunities: {', '.join(opportunities_text) if opportunities_text else 'None'}", 
            font=("Arial", 11),
            fg='white',
            bg='#1c1c1c',
            width=30,
            anchor='w'
        )
        opportunities_label.pack(side=tk.LEFT)
        
        # Row 6: Import Date and Seats Info
        row6 = tk.Frame(basic_info_frame, bg='#1c1c1c')
        row6.pack(fill=tk.X, pady=5)
        
        imported_label = tk.Label(
            row6, 
            text=f"Imported On: {hand_data['imported_on']}", 
            font=("Arial", 11),
            fg='white',
            bg='#1c1c1c',
            anchor='w'
        )
        imported_label.pack(fill=tk.X)
        
        # Row 7: Seats Info
        row7 = tk.Frame(basic_info_frame, bg='#1c1c1c')
        row7.pack(fill=tk.X, pady=5)
        
        seats_label = tk.Label(
            row7, 
            text=f"Seats Info: {hand_data['seats_info']}", 
            font=("Arial", 11),
            fg='white',
            bg='#1c1c1c',
            anchor='w',
            wraplength=750  # Allow wrapping for long text
        )
        seats_label.pack(fill=tk.X)
        
        # Action sections - Hand History
        self.create_action_section(scrollable_frame, "Preflop", hand_data['preflop_all'])
        
        if hand_data['flop_all']:
            self.create_action_section(scrollable_frame, "Flop", hand_data['flop_all'])
        
        if hand_data['turn_all']:
            self.create_action_section(scrollable_frame, "Turn", hand_data['turn_all'])
        
        if hand_data['river_all']:
            self.create_action_section(scrollable_frame, "River", hand_data['river_all'])
        
        return details_frame
        
    def create_action_section(self, parent, title, text):
        """Create a section for displaying action text."""
        if not text:
            return
            
        frame = tk.Frame(parent, bg='#1c1c1c', padx=10, pady=10)
        frame.pack(fill=tk.X, pady=(0, 10))
        
        title_label = tk.Label(
            frame, 
            text=title, 
            font=("Arial", 12, "bold"),
            fg='white',
            bg='#1c1c1c'
        )
        title_label.pack(anchor='w', pady=(0, 5))
        
        text_widget = tk.Text(
            frame, 
            wrap=tk.WORD, 
            bg='#1c1c1c', 
            fg='white',
            height=min(10, len(text.split('\n'))),
            font=("Courier New", 10)
        )
        text_widget.insert(tk.END, text)
        text_widget.config(state=tk.DISABLED)  # Make read-only
        text_widget.pack(fill=tk.X)

    def apply_sort(self):
        #Apply the selected sorting option to the hand history display
        sort_option = self.sort_options.get()
        
        # If "None" is selected, just refresh without sorting
        if sort_option == "None":
            self.refresh_import_tab_no_sort()
            return
        
        # Clear current display
        for row in self.tree.get_children():
            self.tree.delete(row)
        
        # Build query with appropriate ORDER BY clause
        if sort_option == "Date (newest first)":
            order_by = "ORDER BY date_time DESC"
        elif sort_option == "Date (oldest first)":
            order_by = "ORDER BY date_time ASC"
        elif sort_option == "Profit (highest first)":
            order_by = "ORDER BY hero_profit DESC"
        elif sort_option == "Profit (lowest first)":
            order_by = "ORDER BY hero_profit ASC"
        elif sort_option == "Position":
            order_by = "ORDER BY hero_position"
        elif sort_option == "Stake":
            order_by = "ORDER BY stake"
        else:
            order_by = "ORDER BY rowid DESC"  # Default
        
        # Execute query with only the required columns
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        
        query = f"""
            SELECT hand_id, date_time, stake, hero_position, hero_cards, ROUND(hero_profit, 2) as hero_profit
            FROM hands
            {order_by}
        """
        c.execute(query)
        rows = c.fetchall()
        conn.close()
        
        for row in rows:
            # Format the date to show date and time on a single line
            date_parts = row[1].split() if len(row) > 1 and row[1] else ["", ""]
            formatted_date = f"{date_parts[0]} {date_parts[1] if len(date_parts) > 1 else ''}"
            
            # Create a new row with the formatted date
            formatted_row = (formatted_date,) + row[0:1] + row[2:5] + row[5:]
            self.tree.insert("", tk.END, values=formatted_row)

    def generate_hand_combinations(self):
        """Generate all possible poker hand combinations in a standardized format."""
        RANKS = ['A', 'K', 'Q', 'J', 'T', '9', '8', '7', '6', '5', '4', '3', '2']
        hands = []
        
        # Generate pairs
        for rank in RANKS:
            hands.append(f"{rank}{rank}")
        
        # Generate suited and offsuit hands
        for i, rank1 in enumerate(RANKS):
            for rank2 in RANKS[i+1:]:
                hands.append(f"{rank1}{rank2}s")  # suited
                hands.append(f"{rank1}{rank2}o")  # offsuit
        
        return sorted(hands)

    def import_files(self):
        file_paths = filedialog.askopenfilenames(
            title="Select Hand History Files (TXT or ZIP)",
            filetypes=[("Text Files","*.txt"),("ZIP Files","*.zip"),("All Files","*.*")]
        )
        if not file_paths:
            return
        for fp in file_paths:
            if fp.lower().endswith(".zip"):
                txt_files = extract_txt_from_zip(fp)
                for txt in txt_files:
                    hands = parse_hand_history_file(txt)
                    if hands:
                        insert_hand_details(hands)
            elif fp.lower().endswith(".txt"):
                hands = parse_hand_history_file(fp)
                if hands:
                    insert_hand_details(hands)
            else:
                messagebox.showwarning("Unsupported File", f"Skipping {fp}")
        # Refresh all tabs through the main application
        self.main_app.refresh_all_tabs()

    def refresh_import_tab(self):
        for row in self.tree.get_children():
            self.tree.delete(row)
        
        # Apply the current sort option if one is selected
        if hasattr(self, 'sort_options') and self.sort_options.get() and self.sort_options.get() != "None":
            self.apply_sort()
        else:
            # Default behavior - show all hands with newest first
            self.refresh_import_tab_no_sort()

    def on_row_double_click(self, event):
        """Handle double-click on a hand history row."""
        # Check if any item is selected
        selection = self.tree.selection()
        if not selection:
            return  # No item selected, do nothing
        
        item = selection[0]
        values = self.tree.item(item, "values")
        hand_id = values[1]  # Hand ID is now in the second column (index 1)
        
        # Fetch full hand details
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        
        # Get column names
        c.execute("PRAGMA table_info(hands)")
        column_names = [info[1] for info in c.fetchall()]
        
        # Fetch the hand data
        c.execute("SELECT * FROM hands WHERE hand_id = ?", (hand_id,))
        hand_data_tuple = c.fetchone()
        conn.close()
        
        if not hand_data_tuple:
            return
        
        # Convert to dictionary
        hand_data = dict(zip(column_names, hand_data_tuple))
        
        # Create a new window to display hand details
        hand_window = tk.Toplevel(self)
        hand_window.title(f"Hand Details: {hand_id}")
        hand_window.geometry("800x600")
        hand_window.configure(bg=DARK_BG)
        
        # Create hand details frame using the HandDetails class
        HandDetails(hand_window, hand_data)

    def clear_hands(self):
        """Clear all hands from the database after confirmation."""
        result = messagebox.askquestion(
            "Clear All Hands",
            "Are you sure you want to delete all hands from the database?\nThis action cannot be undone.",
            icon='warning'
        )
        
        if result == 'yes':
            conn = sqlite3.connect(DB_FILE)
            c = conn.cursor()
            c.execute("DELETE FROM hands")
            conn.commit()
            conn.close()
            
            # Manually set all position buttons to show 0
            for position, btn in self.main_app.graph_tab.position_buttons.items():
                btn.config(text=f"{position}\nWinloss: $0.00\nHands: 0")
            
            # Refresh all tabs through the main application
            self.main_app.refresh_all_tabs()
        
            messagebox.showinfo("Success", "All hands have been cleared from the database.")


    
    