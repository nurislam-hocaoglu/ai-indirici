"""
FSM (Finite State Machine) states for multi-step conversations.
"""

from aiogram.fsm.state import State, StatesGroup


class DownloadFlow(StatesGroup):
    """States for the /indir flow."""

    searching = State()       # User triggered search, awaiting results display
    selecting = State()       # Results shown, user picking which series
    confirming = State()      # Series detail shown, awaiting confirm/cancel
    choosing_monitor = State()  # User choosing which seasons to monitor
