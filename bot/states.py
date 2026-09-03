"""
FSM (Finite State Machine) states for multi-step conversations.
"""

from aiogram.fsm.state import State, StatesGroup


class DownloadFlow(StatesGroup):
    """States for the /indir flow (Film indirme akışı)."""

    searching = State()   # User triggered search, awaiting results display
    selecting = State()   # Results shown, user picking which movie
    confirming = State()  # Movie detail shown, awaiting confirm/cancel
