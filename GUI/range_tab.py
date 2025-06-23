###############
###  RANGE  ###
###############
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import sqlite3
from constants import DARK_BG, DARK_MEDIUM_BG, TEXT_COLOR, RANKS, DB_FILE, DARK_BUTTON, PROFIT_COLOR, CALL_COLOR
from utils import calculate_range_stats
from parser import parse_hero_contribution, recalculate_all_contributions

class RangeTab(tk.Frame):
    def __init__(self, parent, main_app):
        tk.Frame.__init__(self, parent, bg=DARK_BG)
        self.selected_position = 'All'
        self.GRID_SIZE = 0
        self.main_app = main_app
        self.create_range_tab()

    def create_range_tab(self):
        """Create the range analysis tab with scenario buttons and grid display."""
        DARK_BG = '#1a1a1a'
        DARK_BUTTON = '#2d2d2d'
        TEXT_COLOR = 'white'

        # Create the main container for the range tab
        self.range_frame = tk.Frame(self, bg=DARK_BG)
        self.range_frame.pack(fill=tk.BOTH, expand=True)
        
        # Now you can configure grid weights for self.range_frame
        self.range_frame.grid_rowconfigure(0, weight=19)  # Top section gets 80%
        self.range_frame.grid_rowconfigure(1, weight=1)  # Bottom section gets 20%
        self.range_frame.grid_columnconfigure(0, weight=19)  # Left section gets 80%
        self.range_frame.grid_columnconfigure(1, weight=1)  # Right section gets 20%
        self.range_frame.configure(bg=DARK_BG)
        
        # Create the three main sections inside range_frame:
        # Top left - Range grid
        range_section = tk.Frame(self.range_frame, bg=DARK_BG, bd=1, relief='solid')
        range_section.grid(row=0, column=0, sticky="nsew")
        range_section.bind("<Configure>", self.on_range_grid_configure)
        
        # Top right - Other buttons
        buttons_section = tk.Frame(self.range_frame, bg=DARK_BG, bd=1, relief='solid')
        buttons_section.grid(row=0, column=1, sticky="nsew")
        
        # Bottom - Position buttons
        position_section = tk.Frame(self.range_frame, bg=DARK_BG, bd=1, relief='solid')
        position_section.grid(row=1, column=0, columnspan=2, sticky="nsew")
        
        # Configure the range grid section
        range_section.grid_rowconfigure(0, weight=1)
        range_section.grid_columnconfigure(0, weight=1)
        
        
        # Create legend frame to the left of the grid
        legend_frame = tk.Frame(range_section, bg=DARK_BG)
        legend_frame.pack(side=tk.LEFT, padx=10, pady=10)
        
        # Add legend items
        legend_items = [
            ("Raise", PROFIT_COLOR),
            ("Call", CALL_COLOR),
            ("Fold", DARK_MEDIUM_BG)
        ]
        
        for text, color in legend_items:
            item_frame = tk.Frame(legend_frame, bg=DARK_BG)
            item_frame.pack(anchor='w', pady=5)
            
            color_box = tk.Canvas(item_frame, width=20, height=20, bg=color, highlightthickness=0)
            color_box.pack(side=tk.LEFT, padx=5)
            
            label = tk.Label(item_frame, text=text, bg=DARK_BG, fg=TEXT_COLOR, font=("Arial", 10))
            label.pack(side=tk.LEFT)
        
        # Create the grid frame (inside the RangeTab)
        self.range_grid_frame = tk.Frame(range_section, bg=DARK_BG)
        self.range_grid_frame.pack(expand=True, padx=(150, 0), pady=10, anchor='center')
        self.range_grid_frame.grid_propagate(True)
        self.build_range_square()
        
        # Configure grid weights for centering
        for i in range(13):
            self.range_grid_frame.grid_rowconfigure(i, weight=1)
            self.range_grid_frame.grid_columnconfigure(i, weight=1)
        
        # Configure buttons section
        # Update scenarios and labels
        self.scenarios = ['open', 'faces_open', 'faces_3bet']
        self.scenario_labels = {
            'open': 'Raise First In',
            'faces_open': 'Facing Raise',
            'faces_3bet': 'Facing 3-Bet'
        }
        
        self.selected_scenario = tk.StringVar(value='open')  # Default to 'open'
        
        # Center the buttons vertically in their section
        buttons_section.grid_rowconfigure(0, weight=1)
        buttons_section.grid_columnconfigure(0, weight=1)
        
        # Store this as self.range_buttons_frame instead of button_container
        self.range_buttons_frame = tk.Frame(buttons_section, bg=DARK_BG)
        self.range_buttons_frame.grid(row=0, column=0)
        
        # Create scenario buttons with hand counts
        self.scenario_buttons = {}
        for scenario in self.scenarios:
            button_frame = tk.Frame(self.range_buttons_frame, bg=DARK_BG)
            button_frame.pack(pady=5)
            
            btn = tk.Button(
                button_frame,
                text=self.scenario_labels[scenario],
                bg=DARK_BUTTON,
                fg=TEXT_COLOR,
                width=20,
                height=2,
                font=("Arial", 11),
                command=lambda s=scenario: self.update_range_display(s)
            )
            btn.pack()
            
            # Add hand count label
            count_label = tk.Label(
                button_frame,
                text=self.get_scenario_hand_count(scenario),  # Initialize with actual count
                bg=DARK_BG,
                fg=TEXT_COLOR,
                font=("Arial", 9)
            )
            count_label.pack()
            
            self.scenario_buttons[scenario] = (btn, count_label)
        
        # Configure position section
        position_section.grid_rowconfigure(0, weight=1)
        position_section.grid_columnconfigure(0, weight=1)
        
        position_container = tk.Frame(position_section, bg=DARK_BG)
        position_container.grid(row=0, column=0, pady=3)
        
        # Add 'All' to positions
        positions = ['All', 'BB', 'SB', 'BTN', 'CO', 'HJ', 'UTG']
        self.range_position_buttons = {}
        self.selected_position = None  # Default to None (All positions)
        
        for i, pos in enumerate(positions):
            btn = tk.Button(
                position_container,
                text=pos,
                bg='#00ace6' if pos == 'All' else DARK_BUTTON,  # All is selected by default
                fg=TEXT_COLOR,
                font=("Arial", 10),
                width=15,
                height=2,
                command=lambda p=pos: self.filter_range_by_position(p)
            )
            btn.grid(row=0, column=i, padx=5, pady=3)
            self.range_position_buttons[pos] = btn
        
        # Stats label
        self.range_stats_label = tk.Label(
            range_section, 
            text="", 
            font=("Arial", 10),
            bg=DARK_BG,
            fg=TEXT_COLOR
        )
        self.range_stats_label.pack(side=tk.BOTTOM, pady=5)
        
        # Initial display - show all positions with 'open' scenario
        self.update_range_display('open')
    
    def on_range_grid_configure(self, event):
        current_width = event.width
        current_height = event.height
        self.GRID_SIZE = 0.9 * current_height
        new_square_size = self.GRID_SIZE // 13
        
        # Instead of rebuilding, just update the sizes of existing squares
        if hasattr(self, 'grid_squares'):
            for i in range(13):
                for j in range(13):
                    self.grid_squares[i][j].configure(width=new_square_size, height=new_square_size)
            # Update the display with current scenario
            self.update_range_display(self.selected_scenario.get())

    def build_range_square(self):
        """Create 13x13 grid of canvas widgets."""
        if not hasattr(self, 'grid_squares'):  # Only build if not already built
            SQUARE_SIZE = max(1, self.GRID_SIZE // 13)  # Ensure minimum size of 1
            self.grid_squares = []
            for i in range(13):
                row = []
                for j in range(13):
                    canvas = tk.Canvas(
                        self.range_grid_frame,
                        width=SQUARE_SIZE,
                        height=SQUARE_SIZE,
                        bg=DARK_BG,
                        highlightthickness=1,
                        highlightbackground='white'
                    )
                    canvas.grid(row=i, column=j, sticky="nsew")
                    row.append(canvas)
                self.grid_squares.append(row)
    
    def filter_range_by_position(self, position):
        """Filter range data by selected position"""
        if position == 'All':
            # When All is selected, show data from all positions
            self.selected_position = None
        else:
            if self.selected_position == position:
                self.selected_position = None  # Deselect if already selected
            else:
                self.selected_position = position
        
        # Update button appearances
        for pos, btn in self.range_position_buttons.items():
            if (pos == 'All' and self.selected_position is None) or pos == self.selected_position:
                btn.config(bg='#00ace6')
            else:
                btn.config(bg='#2d2d2d')
        
        # Update hand counts for all scenarios
        for scenario, (_, count_label) in self.scenario_buttons.items():
            count = self.get_scenario_hand_count(scenario)
            count_label.config(text=count)
        
        # Update the range display
        self.update_range_display(self.selected_scenario.get())

    def update_range_display(self, scenario):
        """Update the range grid display for the selected scenario."""
        self.selected_scenario.set(scenario)
        
        # Update button appearances and hand counts
        for s, (btn, count_label) in self.scenario_buttons.items():
            is_selected = (s == scenario)
            btn.config(bg='#00ace6' if is_selected else '#2d2d2d')
            
            # Update hand count for each scenario button
            count = self.get_scenario_hand_count(s)
            count_label.config(text=count)
        
        # Colors for the display
        FOLD_COLOR = "#2d2d2d"   # Light gray-purple
        RAISE_COLOR = "#00ace6"  # Light blue
        CALL_COLOR = "#d571b2"   # Pink
        
        # Get stats
        stats = calculate_range_stats(scenario, self.selected_position)
        
        # Initialize counters
        total_hands = 0
        total_raises = 0
        total_calls = 0
        
        # Update each square in the grid
        for i, r1 in enumerate(RANKS):
            for j, r2 in enumerate(RANKS):
                canvas = self.grid_squares[i][j]
                canvas.delete("all")  # Clear existing content
                
                width = canvas.winfo_reqwidth()
                height = canvas.winfo_reqheight()
                
                # Determine the hand type
                if i == j:  # Pair
                    hand = r1 + r1
                elif i < j:  # Suited
                    hand = r1 + r2 + "s"
                else:  # Offsuit
                    hand = r2 + r1 + "o"
                
                # Get stats: (total, raises, calls, raise%, call%)
                count, raises, calls, raise_pct, call_pct = stats.get(hand, (0, 0, 0, 0, 0))
                
                if count > 0:
                    # Calculate widths for each section
                    fold_pct = 100 - raise_pct - call_pct
                    fold_width = width * fold_pct / 100
                    raise_width = width * raise_pct / 100
                    call_width = width * call_pct / 100
                    
                    # Draw sections in order: Raise, Call, Fold
                    x = 0
                    if raise_pct > 0:
                        canvas.create_rectangle(x, 0, x + raise_width, height, fill=RAISE_COLOR, outline="")
                        x += raise_width
                    if call_pct > 0:
                        canvas.create_rectangle(x, 0, x + call_width, height, fill=CALL_COLOR, outline="")
                        x += call_width
                    if fold_pct > 0:
                        canvas.create_rectangle(x, 0, x + fold_width, height, fill=FOLD_COLOR, outline="")
                    
                    # Add text overlay - just hand name and total count
                    text_color = 'white'
                    canvas.create_text(width/2, height/2, 
                                     text=f"{hand}\n({count})", 
                                     fill=text_color, 
                                     font=("Arial", 9, "bold"),
                                     justify='center')
                else:
                    # Draw empty square
                    canvas.create_rectangle(0, 0, width, height, fill='#1a1a1a', outline="")
                    canvas.create_text(width/2, height/2, text=hand, fill='#666666', font=("Arial", 9))
                
                total_hands += count
                total_raises += raises
                total_calls += calls
        
        # Update stats label
        if total_hands > 0:
            total_raise_pct = (total_raises / total_hands) * 100
            total_call_pct = (total_calls / total_hands) * 100
            self.range_stats_label.config(
                text=f"Total hands: {total_hands}, Raise: {total_raise_pct:.1f}%, Call: {total_call_pct:.1f}%"
            )
        else:
            self.range_stats_label.config(text="No data available")

    def get_scenario_hand_count(self, scenario):
        """Get the total number of hands for a given scenario."""
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        
        query = "SELECT COUNT(*) FROM hands WHERE "
        params = []
        
        # Add scenario-specific conditions
        if scenario == 'open':
            query += "had_rfi_opportunity = 1"
        elif scenario == 'faces_open':
            query += "had_3bet_op = 1"
        elif scenario == 'faces_3bet':
            query += "had_4bet_op = 1"
        else:
            query += "1=1"  # Default case
        
        # Add position filter if selected
        if self.selected_position and self.selected_position != 'All':
            query += " AND hero_position = ?"
            params.append(self.selected_position)
        
        c.execute(query, params)
        count = c.fetchone()[0]
        conn.close()
        
        return f"{count} hands"

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

    def apply_sort(self):
        """Apply the selected sorting option to the hand history display."""
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
        
        # Execute query and update display
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

    def recalculate_all_contributions(self):
        """Recalculate hero contributions for all hands in the database."""
        if messagebox.askyesno("Confirm", "This will recalculate contributions for all hands. Continue?"):
            # Show a progress dialog
            progress_window = tk.Toplevel(self)
            progress_window.title("Recalculating Contributions")
            progress_window.geometry("300x100")
            progress_window.transient(self)
            progress_window.grab_set()
            
            # Center the window
            progress_window.update_idletasks()
            width = progress_window.winfo_width()
            height = progress_window.winfo_height()
            x = (self.winfo_screenwidth() // 2) - (width // 2)
            y = (self.winfo_screenheight() // 2) - (height // 2)
            progress_window.geometry('{}x{}+{}+{}'.format(width, height, x, y))
            
            # Add a label
            label = tk.Label(progress_window, text="Recalculating contributions and adjusted profits...\nThis may take a moment.")
            label.pack(pady=20)
            
            # Update the UI
            progress_window.update()
            
            # Call the recalculation function
            updated_count = recalculate_all_contributions()
            
            # Update the UI again
            progress_window.destroy()
            
            # Also update the adjusted profit based on current rakeback
            self.update_adjusted_profit()
            
            # Show a completion message
            messagebox.showinfo("Recalculation Complete", f"Updated {updated_count} hands.")
            
            # Refresh the display
            self.refresh_import_tab()
            self.refresh_graph_tab()
            self.update_leak_display()

    def refresh_range_tab(self):
        """Refresh the range tab display."""
        # Update the range display with the current scenario
        self.update_range_display(self.selected_scenario.get())
        
        # Update hand counts for all scenarios
        for scenario, (_, count_label) in self.scenario_buttons.items():
            count = self.get_scenario_hand_count(scenario)
            count_label.config(text=count)