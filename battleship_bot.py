#!/usr/bin/env python3
"""
Code Clash Battleship Bot Challenge - CREATE UofT - Winter 2026

YOUR CUSTOM BATTLESHIP BOT STRATEGY
Override the strategy methods below to implement your bot.

===========================================
IMPORTANT:
===========================================
- DO NOT modify battleship_api.py
- ONLY override the 3 strategy methods below
- Use helper methods (starting with _) from the API
- Test your bot with bot_validator.py before submission

Have fun!
"""

import random
from battleship_api import BattleshipBotAPI, run_bot, ABILITY_CODES

class MyBattleshipBot(BattleshipBotAPI):
    def ability_selection(self) -> list:
        """Choose 2 abilities for the entire game."""
        # TODO: Replace with your strategy
        return ["SP", "RF"]  # Example: Sonar Pulse and Rapid Fire
    
    def place_ship_strategy(self, ship_name: str, game_state: dict) -> dict:
        """Place a ship on your board."""
        # TODO: Replace with your strategy
        placed_coords = self._get_placed_coordinates(game_state)
        placement = self._get_random_placement(ship_name, placed_coords)

        if placement:
            return placement
        
        # Fallback
        return {
            "placement": {
                "cell": [0, 0],
                "direction": 'H'
            }
        }
    
    def combat_strategy(self, game_state: dict) -> dict:
        """Choose a combat move."""
        # TODO: Replace with your strategy
        available_abilities = self._get_available_abilities(game_state)
        opponent_grid = self._get_opponent_grid(game_state)
        available_cells = self._get_available_cells(opponent_grid)
        
        if available_cells:
            target = random.choice(available_cells)
        else:
            target = [random.randint(0, 7), random.randint(0, 7)]
        
        return {
            "combat": {
                "cell": target,
                "ability": {"None": {}}
            }
        }

if __name__ == '__main__':
    run_bot(MyBattleshipBot)