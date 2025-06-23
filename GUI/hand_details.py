import tkinter as tk
from tkinter import ttk
from parser import parse_hero_contribution
import os
import google.generativeai as genai
import anthropic
import threading
from PIL import Image, ImageTk
import json

class HandDetails(tk.Frame):
    # Initialize client
    client = None
    api_key = None
    model_type = None
    card_images = {}  # Cache for card images
    base_card_size = (90, 135)  # Base size for cards
    
    @classmethod
    def initialize_model(cls):
        if cls.client is None:
            # Try to load API settings
            try:
                with open('api_settings.json', 'r') as f:
                    settings = json.loads(f.read())
                    cls.api_key = settings.get('api_key')
                    cls.model_type = settings.get('model', "Gemini 2.0 Flash")
            except (FileNotFoundError, json.JSONDecodeError):
                cls.api_key = None
                cls.model_type = "Gemini 2.0 Flash"  # Default model

            if not cls.api_key:
                return False

            # Initialize the client with the appropriate model
            genai.configure(api_key=cls.api_key)
            model_name = "gemini-2.0-flash" if "2.0" in cls.model_type else "gemini-2.5-pro-exp-03-25"
            cls.client = genai.GenerativeModel(model_name)
            return True
        return True

    @classmethod
    def set_api_settings(cls, api_key, model):
        """Set the API settings and reinitialize the client."""
        cls.api_key = api_key
        cls.model_type = model
        cls.client = None  # Force reinitialization
        cls.initialize_model()

    @staticmethod
    def get_card_image(card_code, size=None):
        """Load and cache card images. Card code format: '2h' for 2 of hearts, 'Kc' for King of clubs, etc."""
        if size is None:
            size = HandDetails.base_card_size
            
        if not card_code or len(card_code) != 2:  # Ensure card code is valid
            image_path = os.path.join('Cards', 'cards', 'back.png')
        else:
            # Convert card code to image filename format
            rank = card_code[0].lower()
            suit = card_code[1].lower()
            
            # Map ranks to correct format
            rank_map = {
                't': 'T',
                'j': 'J',
                'q': 'Q',
                'k': 'K',
                'a': 'A'
            }
            
            # Format the rank (if not in rank_map, use the number as is)
            if rank in rank_map:
                rank = rank_map[rank]
            
            # Build filename with rank first, then suit
            image_path = os.path.join('Cards', 'cards', f'{rank}{suit}.png')
            
        # Check if image is already cached
        cache_key = f"{image_path}_{size[0]}_{size[1]}"
        if cache_key not in HandDetails.card_images:
            try:
                img = Image.open(image_path)
                img = img.resize(size, Image.Resampling.LANCZOS)
                HandDetails.card_images[cache_key] = ImageTk.PhotoImage(img)
            except Exception as e:
                print(f"Error loading card image {image_path}: {e}")
                # Load back.png as fallback
                img = Image.open(os.path.join('Cards', 'cards', 'back.png'))
                img = img.resize(size, Image.Resampling.LANCZOS)
                HandDetails.card_images[cache_key] = ImageTk.PhotoImage(img)
                
        return HandDetails.card_images[cache_key]

    @staticmethod
    def format_date_time(date_time_str):
        """Format date and time to show only hours and minutes in AM/PM format."""
        try:
            from datetime import datetime
            if date_time_str == 'N/A':
                return 'N/A'
            
            # Replace forward slashes with hyphens in the date part
            if '/' in date_time_str:
                date_time_str = date_time_str.replace('/', '-')
            
            # Handle both formats: 'YYYY-MM-DD HH:MM:SS' and 'YYYY-MM-DD HH:MM'
            if len(date_time_str.split()) == 2:
                date_str, time_str = date_time_str.split()
                if len(time_str.split(':')) == 3:  # Has seconds
                    time_str = ':'.join(time_str.split(':')[:2])  # Remove seconds
                date_time_str = f"{date_str} {time_str}"
            
            dt = datetime.strptime(date_time_str, '%Y-%m-%d %H:%M')
            return dt.strftime('%Y-%m-%d %I:%M %p')
        except (ValueError, TypeError, AttributeError) as e:
            print(f"Error formatting date: {date_time_str}, Error: {str(e)}")
            return 'N/A'

    def generate_hand_summary(self, hand_data):
        """Generate a succinct, natural-sounding summary of the poker hand as if you're a poker coach reviewing your student's play."""
        try:
            if not self.client:
                self.initialize_model()

            prompt = (
                "Imagine you're an expert poker coach reviewing your student's hand. "
                "Give a brief, natural-sounding summary that covers all the key actions and details using advanced poker terminology. "
                "It should be formatted as a paragraph"
                "Give either one criticism or one compliment about the student's play in the last sentence"
                "Remember to refer to any opponent as 'Villain', and the student as Hero "
                "Don't start with Alright or anything like that, it should be a professional analysis"
                f"Hero is dealt {hand_data.get('hero_cards', 'N/A')} in {hand_data.get('hero_position', 'N/A')} at {hand_data.get('stake', 'N/A')} stakes. "
                f"Preflop, the action goes: {hand_data.get('preflop_all', 'No preflop action available.')}. "
            )
            if (board_flop := hand_data.get('board_flop')):
                prompt += f"On the Flop ({board_flop}), the play is: {hand_data.get('flop_all', 'No flop action available.')}. "
            if (board_turn := hand_data.get('board_turn')):
                prompt += f"At the Turn ({board_turn}), the action reads: {hand_data.get('turn_all', 'No turn action available.')}. "
            if (board_river := hand_data.get('board_river')):
                prompt += f"Finally, on the River ({board_river}), we see: {hand_data.get('river_all', 'No river action available.')}. "
            prompt += (
                f"Outcome: Hero wins ${hand_data.get('hero_profit', '0')} from a ${hand_data.get('total_pot', '0')} pot."
            )

            response = self.client.generate_content(prompt)
            return response.text

        except Exception as e:
            return f"Error generating summary: {str(e)}"

    def __init__(self, parent, hand_data):
        tk.Frame.__init__(self, parent)
        self.hand_data = hand_data
        self.pack(fill=tk.BOTH, expand=True)  # Make the HandDetails frame expand
        self.grid_rowconfigure(0, weight=1)  # Make the frame expand vertically
        self.grid_columnconfigure(0, weight=1)  # Make the frame expand horizontally
        self.main_container = self.create_hand_details_frame(self)  # Pass self as parent
        self.bind_resize_events()

    def bind_resize_events(self):
        """Bind resize events to update card sizes"""
        self.main_container.bind('<Configure>', self.on_window_resize)
        
    def on_window_resize(self, event):
        """Handle window resize events"""
        if event.widget == self.main_container:
            # Calculate new card size based on window width
            window_width = event.width
            base_width = 800  # Base window width for reference
            scale_factor = min(1.5, max(0.5, window_width / base_width))
            
            new_width = int(self.base_card_size[0] * scale_factor)
            new_height = int(self.base_card_size[1] * scale_factor)
            
            # Clear the image cache to force reloading with new size
            self.card_images.clear()
            
            # Update all card images
            if hasattr(self, 'board_cards_frame'):
                for i, widget in enumerate(self.board_cards_frame.winfo_children()):
                    if isinstance(widget, tk.Label):
                        widget.configure(image=self.get_card_image(self.board_cards[i], (new_width, new_height)))
            
            if hasattr(self, 'hero_cards_frame'):
                for i, widget in enumerate(self.hero_cards_frame.winfo_children()):
                    if isinstance(widget, tk.Label):
                        widget.configure(image=self.get_card_image(self.hero_cards[i], (new_width, new_height)))

    def start_generation(self):
        """Start the summary generation in a separate thread"""
        self.generate_button.config(state=tk.DISABLED)
        self.summary_text.config(state=tk.NORMAL)
        self.summary_text.delete(1.0, tk.END)
        
        # Create and show progress bar
        self.progress_frame = tk.Frame(self.summary_frame, bg='#1c1c1c')
        self.progress_frame.pack(fill=tk.X, pady=(5, 0))
        self.progress_label = tk.Label(
            self.progress_frame,
            text="Loading model...",
            fg='white',
            bg='#1c1c1c'
        )
        self.progress_label.pack(side=tk.LEFT)
        self.progress_bar = ttk.Progressbar(
            self.progress_frame,
            mode='indeterminate'
        )
        self.progress_bar.pack(fill=tk.X, expand=True, padx=5)
        self.progress_bar.start(10)
        
        # Start generation in a separate thread
        thread = threading.Thread(target=self.threaded_generation)
        thread.daemon = True
        thread.start()

    def threaded_generation(self):
        """Generate summary in background thread"""
        if not self.client:
            if not self.initialize_model():
                # If initialization failed due to missing API key, update the text box
                self.after(0, self.update_summary_text, 
                    "API key not set. Please set your API key in Tools -> Set API Key")
                # Remove progress bar and re-enable button
                if hasattr(self, 'progress_frame'):
                    self.after(0, self.progress_frame.destroy)
                self.after(0, lambda: self.generate_button.config(state=tk.NORMAL))
                return
            
        self.after(0, self.update_progress_text, "Generating summary...")
        summary = self.generate_hand_summary(self.hand_data)
        self.after(0, self.update_summary_text, summary)
        self.after(0, lambda: self.generate_button.config(state=tk.NORMAL))

    def update_progress_text(self, text):
        """Update the progress text"""
        if hasattr(self, 'progress_label'):
            self.progress_label.config(text=text)

    def update_summary_text(self, summary):
        """Update the summary text in the UI"""
        # Remove progress bar
        if hasattr(self, 'progress_frame'):
            self.progress_frame.destroy()
        
        self.summary_text.config(state=tk.NORMAL)
        self.summary_text.delete(1.0, tk.END)
        self.summary_text.insert(tk.END, summary)
        self.summary_text.config(state=tk.DISABLED)

    def on_generate_summary(self):
        """Handler for generate summary button click"""
        self.start_generation()

    def create_hand_details_frame(self, parent):
        """Create a frame with detailed information about a hand."""
        # Main container that will expand to fill the parent
        main_container = tk.Frame(parent, bg='#1c1c1c')
        main_container.grid(row=0, column=0, sticky='nsew')  # Use grid instead of pack
        
        # Configure grid weights for responsive layout
        main_container.grid_columnconfigure(1, weight=9)  # Main content takes 90%
        main_container.grid_columnconfigure(0, weight=1)  # Left column takes 10%
        main_container.grid_rowconfigure(0, weight=1)  # Make the container expand vertically
        
        # Left column with hand information
        left_column = tk.Frame(main_container, bg='#1c1c1c')
        left_column.grid(row=0, column=0, sticky='nsew', padx=(10, 5), pady=10)
        left_column.grid_columnconfigure(0, weight=1)
        
        # Calculate stack size in BB
        stake_str = self.hand_data.get('stake', 'N/A')
        starting_stack = self.hand_data.get('hero_starting_stack', 0)
        stack_size_bb = 'N/A'
        
        if stake_str != 'N/A' and starting_stack != 0:
            try:
                # Extract the big blind from the stake string (e.g., "$0.1/$0.25" -> 0.25)
                bb = float(stake_str.split('/')[-1].replace('$', ''))
                stack_size_bb = f"{starting_stack / bb:.1f}"
            except (ValueError, IndexError):
                stack_size_bb = 'N/A'
        
        # Hand information labels
        info_items = [
            ("Stake", stake_str),
            ("Position", self.hand_data.get('hero_position', 'N/A')),
            ("Starting Stack", f"${starting_stack:,.2f}"),
            ("Stack Size (BB)", stack_size_bb),
            ("Hand ID", self.hand_data.get('hand_id', 'N/A')),
            ("Date", self.format_date_time(self.hand_data.get('date_time', 'N/A'))),
            ("Hero's Hand", self.hand_data.get('hero_cards', 'N/A'))
        ]
        
        for i, (label, value) in enumerate(info_items):
            # Label frame for each item
            item_frame = tk.Frame(left_column, bg='#1c1c1c')
            item_frame.grid(row=i, column=0, sticky='ew', pady=2)
            item_frame.grid_columnconfigure(0, weight=1)
            
            # Label
            tk.Label(
                item_frame,
                text=label,
                font=("Arial", 10),
                fg='#888888',
                bg='#1c1c1c'
            ).grid(row=0, column=0, sticky='w')
            
            # Value
            tk.Label(
                item_frame,
                text=value,
                font=("Arial", 10, "bold"),
                fg='white',
                bg='#1c1c1c'
            ).grid(row=1, column=0, sticky='w')
        
        # Right content container
        right_container = tk.Frame(main_container, bg='#1c1c1c')
        right_container.grid(row=0, column=1, sticky='nsew', padx=(5, 10), pady=10)
        right_container.grid_columnconfigure(0, weight=1)
        right_container.grid_rowconfigure(1, weight=1)  # Make middle section expand
        
        # Top section with profit/pot (right-aligned)
        top_frame = tk.Frame(right_container, bg='#1c1c1c')
        top_frame.grid(row=0, column=0, sticky='ew', pady=(0, 10))
        top_frame.grid_columnconfigure(0, weight=1)
        
        # Profit display
        profit_frame = tk.Frame(top_frame, bg='#1c1c1c')
        profit_frame.grid(row=0, column=0, sticky='e')
        
        profit_amount = self.hand_data['hero_profit']
        profit_color = '#00ff00' if profit_amount > 0 else '#ff4444' if profit_amount < 0 else 'white'
        
        profit_label = tk.Label(
            profit_frame,
            text=f"${profit_amount:+,.2f}",
            font=("Arial", 16, "bold"),
            fg=profit_color,
            bg='#1c1c1c'
        )
        profit_label.pack(anchor='e')
        
        pot_label = tk.Label(
            profit_frame,
            text=f"Pot: ${self.hand_data['total_pot']:.2f}",
            font=("Arial", 10),
            fg='#888888',
            bg='#1c1c1c'
        )
        pot_label.pack(anchor='e')
        
        # Middle section containing board and hero's hand
        middle_frame = tk.Frame(right_container, bg='#1c1c1c')
        middle_frame.grid(row=1, column=0, sticky='n')  # Stick to top of expanded space
        middle_frame.grid_columnconfigure(0, weight=1)
        
        # Board section
        board_frame = tk.Frame(middle_frame, bg='#1c1c1c')
        board_frame.pack(expand=False, fill='x', pady=(0, 10))
        
        board_label = tk.Label(
            board_frame,
            text="Board",
            font=("Arial", 14, "bold"),
            fg='white',
            bg='#1c1c1c'
        )
        board_label.pack(pady=(0, 10))
        
        # Board cards container
        self.board_cards_frame = tk.Frame(board_frame, bg='#1c1c1c')
        self.board_cards_frame.pack(expand=False)
        
        # Parse board cards from action text
        self.board_cards = [None, None, None, None, None]  # Store card codes as instance variable
        
        # Parse flop cards if flop action exists
        if self.hand_data.get('flop_all'):
            flop_text = self.hand_data['flop_all']
            if '*** FLOP ***' in flop_text and '[' in flop_text:
                flop_cards = flop_text[flop_text.find('[')+1:flop_text.find(']')].split()
                for i, card in enumerate(flop_cards[:3]):
                    self.board_cards[i] = card
        
        # Parse turn card if turn action exists
        if self.hand_data.get('turn_all'):
            turn_text = self.hand_data['turn_all']
            if '*** TURN ***' in turn_text:
                # Find the second occurrence of [ and ]
                first_bracket = turn_text.find('[')
                if first_bracket != -1:
                    second_bracket = turn_text.find('[', first_bracket + 1)
                    if second_bracket != -1:
                        closing_bracket = turn_text.find(']', second_bracket)
                        if closing_bracket != -1:
                            turn_cards = turn_text[second_bracket+1:closing_bracket].split()
                            if turn_cards:
                                self.board_cards[3] = turn_cards[0]
        
        # Parse river card if river action exists
        if self.hand_data.get('river_all'):
            river_text = self.hand_data['river_all']
            if '*** RIVER ***' in river_text:
                # Find the second occurrence of [ and ]
                first_bracket = river_text.find('[')
                if first_bracket != -1:
                    second_bracket = river_text.find('[', first_bracket + 1)
                    if second_bracket != -1:
                        closing_bracket = river_text.find(']', second_bracket)
                        if closing_bracket != -1:
                            river_cards = river_text[second_bracket+1:closing_bracket].split()
                            if river_cards:
                                self.board_cards[4] = river_cards[0]
        
        # Display board cards
        for card in self.board_cards:
            tk.Label(
                self.board_cards_frame,
                image=self.get_card_image(card),
                bg='#1c1c1c'
            ).pack(side=tk.LEFT, padx=5)
        
        # Hero's hand section
        hero_frame = tk.Frame(middle_frame, bg='#1c1c1c')
        hero_frame.pack(expand=False, fill='x', pady=(0, 10))
        
        hero_label = tk.Label(
            hero_frame,
            text="Hero's Hand",
            font=("Arial", 14, "bold"),
            fg='white',
            bg='#1c1c1c'
        )
        hero_label.pack(pady=(0, 10))
        
        # Hero cards container
        self.hero_cards_frame = tk.Frame(hero_frame, bg='#1c1c1c')
        self.hero_cards_frame.pack(expand=False)
        
        # Store hero's cards as instance variable
        self.hero_cards = self.hand_data.get('hero_cards', '').split()
        
        # Display hero's cards
        for card in self.hero_cards:
            tk.Label(
                self.hero_cards_frame,
                image=self.get_card_image(card),
                bg='#1c1c1c'
            ).pack(side=tk.LEFT, padx=5)
        
        # AI Analysis section at the bottom
        self.summary_frame = tk.Frame(right_container, bg='#1c1c1c')
        self.summary_frame.grid(row=2, column=0, sticky='ews')  # Stick to bottom and sides
        self.summary_frame.grid_columnconfigure(0, weight=1)
        
        summary_header = tk.Frame(self.summary_frame, bg='#1c1c1c')
        summary_header.pack(fill=tk.X)
        
        summary_title = tk.Label(
            summary_header,
            text="AI Analysis",
            font=("Arial", 12, "bold"),
            fg='white',
            bg='#1c1c1c'
        )
        summary_title.pack(side=tk.LEFT)
        
        self.generate_button = tk.Button(
            summary_header,
            text="Generate Analysis",
            command=self.on_generate_summary,
            bg='#2c2c2c',
            fg='white',
            relief=tk.FLAT,
            padx=15
        )
        self.generate_button.pack(side=tk.RIGHT)
        
        self.summary_text = tk.Text(
            self.summary_frame,
            wrap=tk.WORD,
            bg='#262626',
            fg='white',
            height=5,
            font=("Arial", 10),
            relief=tk.FLAT,
            padx=10,
            pady=10
        )
        self.summary_text.insert(tk.END, "Click 'Generate Analysis' for AI insights about this hand...")
        self.summary_text.config(state=tk.DISABLED)
        self.summary_text.pack(fill=tk.X, pady=(10, 0))
        
        return main_container