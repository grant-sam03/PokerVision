####################
###  LEAKHELPER  ###
####################

import tkinter as tk
from tkinter import ttk
import sqlite3
from constants import DARK_BG, TEXT_COLOR, ACCENT_COLOR, DARK_MEDIUM_BG, PROFIT_COLOR, LOSS_COLOR, LIGHT_BG, RANKS, DB_FILE, DARK_PROFIT_COLOR, DARK_LOSS_COLOR
from utils import calculate_profit_stats
from GUI.hand_details import HandDetails

class LeakHelperTab(tk.Frame):
    def __init__(self, parent, main_app):
        tk.Frame.__init__(self, parent, bg=DARK_BG)
        self.main_app = main_app
        self.GRID_SIZE = 0
        self.style = main_app.style  # Use the main app's style
        self.create_leak_tab()

    def create_leak_tab(self):
        """Create the LeakHelper tab with profit/loss grid display."""

        self.leak_frame = tk.Frame(self, bg=DARK_BG)
        self.leak_frame.pack(fill=tk.BOTH, expand=True)
        
        # Configure grid weights for the main frame
        self.leak_frame.grid_rowconfigure(0, weight=49)  # Top section gets 80%
        self.leak_frame.grid_rowconfigure(1, weight=1)  # Bottom section gets 20%    
        # Adjust column weights to make hand_selection column smaller
        self.leak_frame.grid_columnconfigure(0, weight=1)  # Left section made slightly smaller
        self.leak_frame.grid_columnconfigure(1, weight=48)  # Middle section increased
        self.leak_frame.grid_columnconfigure(2, weight=1)  # Right section unchanged
        self.leak_frame.configure(bg=DARK_BG)
        
        # Create the three main sections (like Range tab)
        # Top left - Hand Data
        hand_selection = tk.Frame(self.leak_frame, bg=DARK_BG, bd=2, relief='solid')
        hand_selection.grid(row=0, column=0, rowspan=2, sticky="nsew")
        
        # Configure hand_selection grid with more elegant spacing
        hand_selection.grid_rowconfigure(0, weight=1)  # Selected hand display
        hand_selection.grid_rowconfigure(1, weight=1)  # Best hands
        hand_selection.grid_rowconfigure(2, weight=6)  # Worst hands
        hand_selection.grid_columnconfigure(0, weight=1)
        
        # Create selected hand display frame at the top with more elegant styling
        selected_hand_frame = tk.Frame(hand_selection, bg=DARK_BG)
        selected_hand_frame.grid(row=0, column=0, sticky="nsew", padx=20, pady=(0, 0))
        
        # Create a canvas for the selected hand display with a more elegant border
        self.selected_hand_canvas = tk.Canvas(
            selected_hand_frame,
            width=120,
            height=120,
            bg=DARK_BG,
            highlightthickness=0,
            highlightbackground=LIGHT_BG
        )
        self.selected_hand_canvas.pack(pady=10)
        
        
        # Create best hands frame with more elegant styling
        best_hands_frame = tk.Frame(hand_selection, bg=DARK_BG)
        best_hands_frame.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0, 0))
        
        # Create worst hands frame with more elegant styling
        worst_hands_frame = tk.Frame(hand_selection, bg=DARK_BG)
        worst_hands_frame.grid(row=2, column=0, sticky="nsew", padx=10, pady=(0, 20))
        
        
        # Configure the style for the treeviews with more elegant styling
        self.style.configure("Treeview", 
                        background=DARK_MEDIUM_BG, 
                        foreground=TEXT_COLOR, 
                        fieldbackground=DARK_MEDIUM_BG,
                        rowheight=25,
                        font=("Arial", 10))  # Increased font size
        self.style.configure("Treeview.Heading", 
                        background=DARK_BG, 
                        foreground=TEXT_COLOR,
                        font=("Arial", 10, "bold"))
        self.style.map('Treeview', background=[('selected', ACCENT_COLOR)])

        
        

        
        # Create best hands treeview
        best_tree_frame = tk.Frame(best_hands_frame, bg=DARK_BG)
        best_tree_frame.pack(fill=tk.BOTH, expand=True)
        
        # Create treeview without scrollbar since we only show 5 items
        self.best_hands_tree = ttk.Treeview(best_tree_frame, 
                                           columns=("position", "stake", "profit"), 
                                           show="headings",
                                           height=5,
                                           style="Treeview")  # Exactly 5 rows
        self.best_hands_tree.pack(fill=tk.X, expand=False)  # Only expand horizontally
        
        # Configure best hands columns
        self.best_hands_tree.heading("position", text="Position")
        self.best_hands_tree.heading("stake", text="Stake")
        self.best_hands_tree.heading("profit", text="Profit")
        
        self.best_hands_tree.column("position", width=70, anchor=tk.CENTER)
        self.best_hands_tree.column("stake", width=70, anchor=tk.CENTER)
        self.best_hands_tree.column("profit", width=80, anchor=tk.CENTER)
        
        # Configure the header style for best hands
        self.style.map("BestHands.Treeview.Heading",
                  background=[('active', PROFIT_COLOR)],
                  foreground=[('active', TEXT_COLOR)])
        self.style.configure("BestHands.Treeview.Heading", 
                        background=PROFIT_COLOR, 
                        foreground=TEXT_COLOR,
                        font=("Arial", 10, "bold"))
        
        # Apply custom tag for best hands rows
        self.style.configure("BestHands.Treeview", 
                        background=DARK_MEDIUM_BG, 
                        foreground=TEXT_COLOR,
                        fieldbackground=DARK_MEDIUM_BG,
                        font=("Arial", 10))
        self.best_hands_tree.configure(style="BestHands.Treeview")
        
        # Bind double-click event for best hands
        self.best_hands_tree.bind("<Double-1>", self.on_best_hand_double_click)
        
        # Create worst hands treeview
        worst_tree_frame = tk.Frame(worst_hands_frame, bg=DARK_BG)
        worst_tree_frame.pack(fill=tk.BOTH, expand=True)
        
        # Create treeview without scrollbar since we only show 5 items
        self.worst_hands_tree = ttk.Treeview(worst_tree_frame, 
                                            columns=("position", "stake", "profit"), 
                                            show="headings",
                                            height=5)  # Exactly 5 rows
        self.worst_hands_tree.pack(fill=tk.X, expand=False)  # Only expand horizontally
        
        # Configure worst hands columns
        self.worst_hands_tree.heading("position", text="Position")
        self.worst_hands_tree.heading("stake", text="Stake")
        self.worst_hands_tree.heading("profit", text="Profit")
        
        self.worst_hands_tree.column("position", width=70, anchor=tk.CENTER)
        self.worst_hands_tree.column("stake", width=70, anchor=tk.CENTER)
        self.worst_hands_tree.column("profit", width=80, anchor=tk.CENTER)  # Center the profit column
        
        # Configure the header style for worst hands
        self.style.map("WorstHands.Treeview.Heading",
                  background=[('active', LOSS_COLOR)],
                  foreground=[('active', TEXT_COLOR)])
        self.style.configure("WorstHands.Treeview.Heading", 
                        background=LOSS_COLOR, 
                        foreground=TEXT_COLOR,
                        font=("Arial", 10, "bold"))
        
        # Apply custom tag for worst hands rows
        self.style.configure("WorstHands.Treeview", 
                        background=DARK_MEDIUM_BG, 
                        foreground=TEXT_COLOR,
                        fieldbackground=DARK_MEDIUM_BG,
                        font=("Arial", 10))
        self.worst_hands_tree.configure(style="WorstHands.Treeview")
        
        # Bind double-click event for worst hands
        self.worst_hands_tree.bind("<Double-1>", self.on_worst_hand_double_click)
        
        # Center - Profit/Loss grid
        leak_section = tk.Frame(self.leak_frame, bg=DARK_BG, bd=2)
        leak_section.grid(row=0, column=1, rowspan=2, sticky="nsew", pady= (0, 75))
        leak_section.grid_propagate(True)
        leak_section.bind("<Configure>", self.on_leak_grid_configure)
        
        # Top right - Scenario buttons
        scenario_section = tk.Frame(self.leak_frame, bg=DARK_BG, bd=2, relief='solid')
        scenario_section.grid(row=0, column=2, rowspan=2, sticky="nsew")
        scenario_section.grid_propagate(True)
        
        # Bottom - Position buttons
        position_section = tk.Frame(self.leak_frame, bg=DARK_BG, bd=2, relief='solid')
        position_section.grid(row=1, column=0, columnspan=3, sticky="nsew")
        position_section.grid_propagate(True)
        
        # Configure the leak grid section
        leak_section.grid_rowconfigure(0, weight=1)
        leak_section.grid_columnconfigure(0, weight=1)
        
        # Create legend frame to the right of the grid
        legend_frame = tk.Frame(leak_section, bg=DARK_BG)
        legend_frame.pack(side=tk.LEFT, padx=10, pady=10)
        
        # Add legend items
        legend_items = [
            ("Profit", PROFIT_COLOR),  # Light blue for profit
            ("Loss", LOSS_COLOR)     # Red for loss
        ]
        
        for text, color in legend_items:
            item_frame = tk.Frame(legend_frame, bg=DARK_BG)
            item_frame.pack(anchor='w', pady=5)
            
            color_box = tk.Canvas(item_frame, width=20, height=20, bg=color, highlightthickness=0)
            color_box.pack(side=tk.LEFT, padx=5)
            
            label = tk.Label(item_frame, text=text, bg=DARK_BG, fg=TEXT_COLOR, font=("Arial", 10))
            label.pack(side=tk.LEFT)
        
        # Create grid frame with fixed size and centered in the column
        # (ignoring the legend frame for centering purposes)
        self.leak_grid_frame = tk.Frame(leak_section, bg=DARK_BG)
        self.leak_grid_frame.pack(expand=True, padx=(0, 0), pady=10, anchor='center')
        self.leak_grid_frame.grid_propagate(True)
        
        # Configure grid weights for centering
        for i in range(13):
            self.leak_grid_frame.grid_rowconfigure(i, weight=1)
            self.leak_grid_frame.grid_columnconfigure(i, weight=1)
        
        # Initialize grid size
        self.build_leak_squares()
        
        # Configure scenario section (right side)
        scenario_section.grid_rowconfigure(0, weight=1)
        scenario_section.grid_columnconfigure(0, weight=1)

        # Configure hand selection section (left side)
        hand_selection.grid_rowconfigure(0, weight=1)
        hand_selection.grid_columnconfigure(0, weight=1)
        
        # Preflop scenario buttons container
        scenario_container = tk.Frame(scenario_section, bg=DARK_BG)
        scenario_container.grid(row=0, column=0, padx=5)
        
        # Add preflop scenario buttons
        scenarios = ['All', 'Open', 'Facing Open', '3bet', 'Facing 3bet', '4bet', 'Facing 4bet', '5bet+']
        self.leak_scenario_buttons = {}
        self.leak_selected_scenario = None  # Default to None (All scenarios)
        
        for i, scenario in enumerate(scenarios):
            button_frame = tk.Frame(scenario_container, bg=DARK_BG)
            button_frame.pack(pady=5)
            
            btn = tk.Button(
                button_frame,
                text=scenario,
                bg=ACCENT_COLOR if scenario == 'All' else DARK_MEDIUM_BG,  # All is selected by default
                fg=TEXT_COLOR,
                font=("Arial", 11),
                width=20,
                height=2,
                command=lambda s=scenario: self.filter_leak_by_scenario(s)
            )
            btn.pack(fill=tk.BOTH, expand=True)
            self.leak_scenario_buttons[scenario] = btn
        
        # Configure position section
        position_section.grid_rowconfigure(0, weight=1)
        position_section.grid_columnconfigure(1, weight=1)
        
        # Position buttons container
        position_container = tk.Frame(position_section, bg=DARK_BG)
        position_container.grid(row=0, column=1, padx=(130, 0), pady=3)
        
        # Configure the container's grid for button spacing
        for i in range(13):  # Match grid columns
            position_container.grid_columnconfigure(i, weight=1)
        
        # Add 'All' to positions
        positions = ['All', 'BB', 'SB', 'BTN', 'CO', 'HJ', 'UTG']
        self.leak_position_buttons = {}
        self.leak_selected_position = None  # Default to None (All positions)
        
        # Calculate starting column to center BTN (index 3) at grid column 7 (8th box)
        start_col = 7 - 3  # Grid column 7 (8th box) minus BTN position (index 3)
        
        for i, pos in enumerate(positions):
            btn = tk.Button(
                position_container,
                text=pos,
                bg=ACCENT_COLOR if pos == 'All' else DARK_MEDIUM_BG,  # All is selected by default
                fg=TEXT_COLOR,
                font=("Arial", 10),
                width=15,
                height=2,
                command=lambda p=pos: self.filter_leak_by_position(p)
            )
            btn.grid(row=0, column=start_col + i, padx=5, pady=0)
            self.leak_position_buttons[pos] = btn
        
        # Stats label
        self.leak_stats_label = tk.Label(
            leak_section, 
            text="", 
            font=("Arial", 10),
            bg=DARK_BG,
            fg=TEXT_COLOR
        )
        
        # Initialize default selected hand (AA)
        self.hand_filter = "AA"
        
        # Initial display - show all positions
        self.update_leak_display()
        
        # Initialize the selected hand display with AA (index 0,0 for AA)
        self.update_selected_hand_display(0, 0)

    def filter_leak_by_position(self, position):
        """Filter leak data by selected position"""
        if position == 'All':
            # When All is selected, show data from all positions
            self.leak_selected_position = None
        else:
            if self.leak_selected_position == position:
                self.leak_selected_position = None  # Deselect if already selected
            else:
                self.leak_selected_position = position
        
        # Update button appearances
        for pos, btn in self.leak_position_buttons.items():
            if (pos == 'All' and self.leak_selected_position is None) or pos == self.leak_selected_position:
                btn.config(bg=ACCENT_COLOR)
            else:
                btn.config(bg=DARK_MEDIUM_BG)
        
        # Update the leak display
        self.update_leak_display()
        
    def filter_leak_by_scenario(self, scenario):
        """Filter leak data by selected preflop scenario"""
        if scenario == 'All':
            # When All is selected, show data from all scenarios
            self.leak_selected_scenario = None
        else:
            if self.leak_selected_scenario == scenario:
                self.leak_selected_scenario = None  # Deselect if already selected
            else:
                self.leak_selected_scenario = scenario
        
        # Update button appearances
        for s, btn in self.leak_scenario_buttons.items():
            if (s == 'All' and self.leak_selected_scenario is None) or s == self.leak_selected_scenario:
                btn.config(bg=ACCENT_COLOR)
            else:
                btn.config(bg=DARK_MEDIUM_BG)
        
        # Update the leak display
        self.update_leak_display()

    def update_leak_display(self):
        """Update the leak grid display with profit/loss data."""
        # Get profit stats
        stats = calculate_profit_stats(self.leak_selected_position, self.leak_selected_scenario)
        
        # Initialize counters
        total_hands = 0
        total_profit = 0
        profitable_hands = 0
        
        # Update each square in the grid
        for i, r1 in enumerate(RANKS):
            for j, r2 in enumerate(RANKS):
                canvas = self.leak_squares[i][j]
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
                
                # Get stats: (count, total_profit, avg_profit)
                count, profit, avg_profit = stats.get(hand, (0, 0, 0))
                
                if count > 0:
                    # Determine color based on profit and selection
                    if hand == self.hand_filter:  # If this is the selected hand
                        if profit >= 0:
                            color = DARK_PROFIT_COLOR  # Darker blue for selected profit
                        else:
                            color = DARK_LOSS_COLOR  # Darker red for selected loss
                    else:  # Not selected
                        if profit >= 0:
                            color = PROFIT_COLOR  # Light blue for profit
                        else:
                            color = LOSS_COLOR  # Red for loss
                    
                    # Draw background
                    canvas.create_rectangle(0, 0, width, height, fill=color, outline="")
                    
                    # Format profit for display
                    profit_display = f"${profit:.2f}"
                    
                    # Add text overlay - hand name and profit only (no hand count)
                    canvas.create_text(width/2, height/2, 
                                     text=f"{hand}\n{profit_display}", 
                                     fill=TEXT_COLOR, 
                                     font=("Arial", 9, "bold"),
                                     justify='center')
                    
                    # Update counters
                    total_hands += count
                    total_profit += profit
                    if profit > 0:
                        profitable_hands += 1
                else:
                    # Draw empty square
                    canvas.create_rectangle(0, 0, width, height, fill=DARK_BG, outline="")
                    canvas.create_text(width/2, height/2, text=hand, fill='#666666', font=("Arial", 9))
        
        # Update stats label
        if total_hands > 0:
            profitable_pct = (profitable_hands / len(stats)) * 100 if len(stats) > 0 else 0
            self.leak_stats_label.config(
                text=f"Total hands: {total_hands}, Total profit: ${total_profit:.2f}, Profitable hands: {profitable_pct:.1f}%"
            )
        else:
            self.leak_stats_label.config(text="No data available")
        
        # Find the indices for the current hand_filter
        for i, r1 in enumerate(RANKS):
            for j, r2 in enumerate(RANKS):
                if i == j and r1 + r1 == self.hand_filter:  # Pair
                    self.update_selected_hand_display(i, j)
                    break
                elif i < j and r1 + r2 + "s" == self.hand_filter:  # Suited
                    self.update_selected_hand_display(i, j)
                    break
                elif i > j and r2 + r1 + "o" == self.hand_filter:  # Offsuit
                    self.update_selected_hand_display(i, j)
                    break
            
        # Update best and worst hands treeviews
        self.update_best_worst_hands()

    def update_best_worst_hands(self):
        """Update the best and worst hands treeviews based on current filters."""
        # Clear existing items
        for item in self.best_hands_tree.get_children():
            self.best_hands_tree.delete(item)
        
        for item in self.worst_hands_tree.get_children():
            self.worst_hands_tree.delete(item)
        
        # Get best and worst hands
        best_hands, worst_hands = get_best_worst_hands(
            position=self.leak_selected_position,
            scenario=self.leak_selected_scenario,
            hand=self.hand_filter,
            limit=5
        )
        
        # Populate best hands treeview
        for i, (hand_id, position, stake, cards, profit) in enumerate(best_hands):
            # Format profit as currency
            profit_display = f"${profit:.2f}"
            
            # Store hand_id as a hidden tag for retrieval on double-click
            self.best_hands_tree.insert("", "end", values=(position, stake, profit_display), tags=(hand_id,))
        
        # Populate worst hands treeview
        for i, (hand_id, position, stake, cards, profit) in enumerate(worst_hands):
            # Format profit as currency
            profit_display = f"${profit:.2f}"
            
            # Store hand_id as a hidden tag for retrieval on double-click
            self.worst_hands_tree.insert("", "end", values=(position, stake, profit_display), tags=(hand_id,))
    
    def on_leak_square_click(self, i, j):
        """Handle click on a leak grid square."""
        # Determine the hand type
        if i == j:  # Pair
            hand = RANKS[i] + RANKS[i]
        elif i < j:  # Suited
            hand = RANKS[i] + RANKS[j] + "s"
        else:  # Offsuit
            hand = RANKS[j] + RANKS[i] + "o"
        
        # Update hand_filter
        self.hand_filter = hand
        
        # Update the selected hand display
        self.update_selected_hand_display(i, j)
        
        # Update the display to show the selected square
        self.update_leak_display()
        
    def update_selected_hand_display(self, i, j):
        """Update the selected hand display canvas with the currently selected hand."""
        # Clear the canvas
        self.selected_hand_canvas.delete("all")
        
        width = self.selected_hand_canvas.winfo_width()
        height = self.selected_hand_canvas.winfo_height()
        
        # If width or height is 1, the canvas hasn't been properly sized yet
        # Use the configured size instead
        if width <= 1:
            width = 120
        if height <= 1:
            height = 120
        
        # Determine the hand type
        if i == j:  # Pair
            hand = RANKS[i] + RANKS[i]
        elif i < j:  # Suited
            hand = RANKS[i] + RANKS[j] + "s"
        else:  # Offsuit
            hand = RANKS[j] + RANKS[i] + "o"
        
        # Get stats for this hand
        stats = calculate_profit_stats(self.leak_selected_position, self.leak_selected_scenario)
        count, profit, avg_profit = stats.get(hand, (0, 0, 0))
        
        # Determine color based on profit
        if count > 0:
            if profit >= 0:
                color = DARK_PROFIT_COLOR  # Darker blue for selected profit
                border_color = PROFIT_COLOR  # Light blue border
            else:
                color = DARK_LOSS_COLOR  # Darker red for selected loss
                border_color = LOSS_COLOR  # Light red border
        else:
            color = DARK_BG  # Dark background for no data
            border_color = LIGHT_BG  # Gray border
        
        # Draw background with rounded corners
        self.selected_hand_canvas.create_rectangle(
            2, 2, width-2, height-2, 
            fill=border_color, 
            outline=color,
            width=2
        )
        
        # Format profit for display
        profit_display = f"${profit:.2f}" if count > 0 else "No data"
        
        # Draw hand name in larger font
        self.selected_hand_canvas.create_text(
            width/2, 
            height/2 - 10, 
            text=hand, 
            fill=TEXT_COLOR, 
            font=("Arial", 18, "bold"),
            justify='center'
        )
        
        # Draw profit in smaller font below
        self.selected_hand_canvas.create_text(
            width/2, 
            height/2 + 20, 
            text=profit_display, 
            fill=TEXT_COLOR, 
            font=("Arial", 14),
            justify='center'
        )
    
    def _show_hand_details(self, hand_id):
        """Helper method to show hand details in a new window."""
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

    def on_best_hand_double_click(self, event):
        """Handle double-click on a best hand in the treeview."""
        selected = self.best_hands_tree.selection()
        if not selected:
            return
            
        # Get the hand_id from the tag
        hand_id = self.best_hands_tree.item(selected[0], "tags")[0]
        self._show_hand_details(hand_id)

    def on_worst_hand_double_click(self, event):
        """Handle double-click on a worst hand in the treeview."""
        selected = self.worst_hands_tree.selection()
        if not selected:
            return
            
        # Get the hand_id from the tag
        hand_id = self.worst_hands_tree.item(selected[0], "tags")[0]
        self._show_hand_details(hand_id)

    def update_adjusted_profit(self):
        """Update the adjusted_profit column for all hands based on current rakeback percentage."""
        try:
            # Get the rakeback percentage
            rakeback_pct = float(self.rakeback_var.get()) / 100.0
            
            # Ensure rakeback percentage is between 0 and 1
            rakeback_pct = max(0.0, min(1.0, rakeback_pct))
            
            conn = sqlite3.connect(DB_FILE)
            c = conn.cursor()
            
            # Update adjusted_profit for all hands
            # For 100% rakeback, use hero_profit_with_rake for winning hands
            if rakeback_pct == 1.0:
                c.execute("""
                    UPDATE hands
                    SET adjusted_profit = hero_profit_with_rake
                    WHERE hero_profit > 0
                """)
            else:
                # Formula: adjusted_profit = hero_profit + (rake * rakeback_percentage) for winning hands only
                c.execute("""
                    UPDATE hands
                    SET adjusted_profit = hero_profit + (rake * ?)
                    WHERE hero_profit > 0
                """, (rakeback_pct,))
            
            # For hands where hero didn't win, adjusted_profit = hero_profit
            c.execute("""
                UPDATE hands
                SET adjusted_profit = hero_profit
                WHERE hero_profit <= 0
            """)
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            print(f"Error updating adjusted profit: {e}")

    def on_leak_grid_configure(self, event):
        """Handle grid frame resize events."""
        current_width = event.width
        current_height = event.height
        self.GRID_SIZE = 0.9 * current_height
        new_square_size = self.GRID_SIZE // 13
        
        # Instead of rebuilding, just update the sizes of existing squares
        if hasattr(self, 'leak_squares'):
            for i in range(13):
                for j in range(13):
                    self.leak_squares[i][j].configure(width=new_square_size, height=new_square_size)
            # Update the display with current data
            self.update_leak_display()

    def build_leak_squares(self):
        """Create 13x13 grid of canvas widgets."""
        if not hasattr(self, 'leak_squares'):  # Only build if not already built
            SQUARE_SIZE = max(1, self.GRID_SIZE // 13)  # Ensure minimum size of 1
            self.leak_squares = []
            for i in range(13):
                row = []
                for j in range(13):
                    canvas = tk.Canvas(
                        self.leak_grid_frame,
                        width=SQUARE_SIZE,
                        height=SQUARE_SIZE,
                        bg=DARK_BG,
                        highlightthickness=1,
                        highlightbackground=TEXT_COLOR
                    )
                    canvas.grid(row=i, column=j, sticky="nsew")
                    # Add click binding to each canvas
                    canvas.bind('<Button-1>', lambda e, i=i, j=j: self.on_leak_square_click(i, j))
                    row.append(canvas)
                self.leak_squares.append(row)



def get_best_worst_hands(position=None, scenario=None, hand=None, limit=5):
    """Get the best and worst performing hands based on filters."""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    
    # Base query - include hand_id for double-click functionality
    query = """
        SELECT hand_id, hero_position, stake, hero_cards, hero_profit
        FROM hands
        WHERE hero_cards IS NOT NULL AND hero_cards != ''
    """
    params = []
    
    # Add filters
    if position:
        query += " AND hero_position = ?"
        params.append(position)
    
    if scenario:
        # Map button labels to actual scenario values in the database
        scenario_mapping = {
            'Open': 'open (single raised)',
            'Facing Open': 'call_vs_open (single raised)',
            '3bet': '3bet',
            'Facing 3bet': 'call_vs_3bet',
            '4bet': '4bet',
            'Facing 4bet': 'call_vs_4bet+',
            '5bet+': '5bet+'
        }
        
        if scenario in scenario_mapping:
            query += " AND preflop_scenario = ?"
            params.append(scenario_mapping[scenario])
    
    if hand:
        # Add hand filter based on the selected hand in the grid
        if len(hand) == 2:  # Pair
            rank = hand[0]
            query += " AND hero_cards LIKE ? AND substr(hero_cards, 1, 1) = ? AND substr(hero_cards, 4, 1) = ?"
            params.extend([f"%{rank}%", rank, rank])
        elif len(hand) == 3:  # Suited or offsuit
            rank1, rank2 = hand[0], hand[1]
            suited = hand.endswith('s')
            if suited:
                query += " AND hero_cards LIKE ? AND hero_cards LIKE ? AND substr(hero_cards, 2, 1) = substr(hero_cards, 5, 1)"
                params.extend([f"%{rank1}%", f"%{rank2}%"])
            else:
                query += " AND hero_cards LIKE ? AND hero_cards LIKE ? AND substr(hero_cards, 2, 1) != substr(hero_cards, 5, 1)"
                params.extend([f"%{rank1}%", f"%{rank2}%"])
    
    # Get best hands (only positive profit)
    best_query = query + " AND hero_profit > 0 ORDER BY hero_profit DESC LIMIT ?"
    c.execute(best_query, params + [limit])
    best_hands = c.fetchall()
    
    # Get worst hands (only negative profit)
    worst_query = query + " AND hero_profit < 0 ORDER BY hero_profit ASC LIMIT ?"
    c.execute(worst_query, params + [limit])
    worst_hands = c.fetchall()
    
    conn.close()
    return best_hands, worst_hands