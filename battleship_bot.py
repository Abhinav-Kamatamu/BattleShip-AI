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
from battleship_api import BattleshipBotAPI, run_bot


class MyBattleshipBot(BattleshipBotAPI):

    def __init__(self):
        super().__init__()
        self.ship_dimensions = [(1, 4), (1, 3), (2, 3), (1, 2)]

    def ability_selection(self) -> list:
        """Choose 2 abilities for the entire game."""
        return ["HS", "SD"]

    def place_ship_strategy(self, ship_name: str, game_state: dict) -> dict:
        """
        Place a ship on your board.
        """
        empty_grid = [['N'] * 8 for _ in range(8)] # Create an empty_grid
        heatmap = self._calculate_probability_map(empty_grid) # Create an "initial" heatmap for an empty grid.

        placed_coords = self._get_placed_coordinates(game_state)

        # To ensure we dont' place ships touching each other
        forbidden_buffer = set()
        for r, c in placed_coords:
            for dr, dc in [(0, 1), (0, -1), (1, 0), (-1, 0)]:
                nr, nc = r + dr, c + dc
                if 0 <= nr < 8 and 0 <= nc < 8:
                    forbidden_buffer.add((nr, nc))
        # Don't do corners
        forbidden_buffer.add((0,0))
        forbidden_buffer.add((7,0))
        forbidden_buffer.add((0,7))
        forbidden_buffer.add((7,7))

        # Sort board cells by probability
        cells_with_prob = []
        for r in range(8):
            for c in range(8):
                cells_with_prob.append(((r, c), heatmap[r][c]))

        cells_with_prob.sort(key=lambda x: x[1])

        # Place the ships
        for (r, c), prob in cells_with_prob:
            for orientation in ['H', 'V']:
                ship_cells = self._get_ship_cells(ship_name, r, c, orientation)

                # Skip invalid bounds
                if not ship_cells:
                    continue

                if not self._is_valid_placement(ship_cells, placed_coords):
                    continue

                # Must not touch existing ships
                if any(cell in forbidden_buffer for cell in ship_cells):
                    continue

                return {
                    "placement": {
                        "name": ship_name,
                        "cell": [r, c],
                        "direction": orientation
                    }
                }


        # Fallback (Should typically not be reached)
        return self._get_random_placement(ship_name, placed_coords)

    def combat_strategy(self, game_state: dict) -> dict:
        """Choose a combat move based on Probability Density."""
        opponent_grid = self._get_opponent_grid(game_state)
        available_abilities = self._get_available_abilities(game_state)
        my_ships = self._get_own_ships(game_state)

        # Use Hailstorm if it is the first move
        is_start_of_game = all(cell == 'N' for row in opponent_grid for cell in row)
        if is_start_of_game and "HS" in available_abilities:
            return {
                "combat": {
                    "cell": [0, 0],  # Cell ignored for HS
                    "ability": {"HS": {}}
                }
            }

        # Use Shield if more than 5 hits taken
        total_hits_taken = sum(len(ship.get("hits", [])) for ship in my_ships)
        if total_hits_taken > 5 and "SD" in available_abilities:
            target_ship_coord = self._get_best_shield_target(my_ships)
            if target_ship_coord:
                return {
                    "combat": {
                        "cell": target_ship_coord,
                        "ability": {"SD": target_ship_coord}
                    }
                }

        # Taking shots
        heatmap = self._calculate_probability_map(opponent_grid)

        available_cells = self._get_available_cells(opponent_grid)

        # Map available cells to their heatmap scores
        candidates = []
        for cell in available_cells:
            r, c = cell
            score = heatmap[r][c]
            candidates.append((score, cell))

        # Shuffle equal scores
        random.shuffle(candidates)

        best_cell = [0, 0]
        if candidates:
            # Pick the one with highest probability score
            best_cell = max(candidates, key=lambda x: x[0])[1]
        else:
            best_cell = [random.randint(0, 7), random.randint(0, 7)]

        return {
            "combat": {
                "cell": best_cell,
                "ability": {"None": {}}
            }
        }

    # ------------------------------------------------------------------------
    # MY HELPER METHODS
    # ------------------------------------------------------------------------

    def _calculate_probability_map(self, grid: list) -> list:
        """
        Generates an 8x8 grid where each cell's value represents the probability
        of a ship occupying that cell.
        """
        heatmap = [[0.0] * 8 for _ in range(8)]

        # Weights
        BASE_WEIGHT = 1
        HIT_WEIGHT = 100

        # Superposition of all ship types
        for r_dim, c_dim in self.ship_dimensions:

            # Generate offsets for given shape
            offsets = []
            for r in range(r_dim):
                for c in range(c_dim):
                    offsets.append((r, c))
            self._add_configuration_weights(grid, heatmap, offsets, BASE_WEIGHT, HIT_WEIGHT)

            # Generate offsets for rotated shape (which always happens)
            if r_dim != c_dim:
                offsets_rotated = []
                for r in range(c_dim):  # Swap dimentionss
                    for c in range(r_dim):
                        offsets_rotated.append((r, c))
                self._add_configuration_weights(grid, heatmap, offsets_rotated, BASE_WEIGHT, HIT_WEIGHT)

        # Zero out known cells (can't shoot where we already shot)
        for r in range(8):
            for c in range(8):
                if grid[r][c] != 'N':
                    heatmap[r][c] = 0

        return heatmap

    def _add_configuration_weights(self, grid, heatmap, offsets, base_weight, hit_weight):
        """Helper to slide a specific ship shape over the grid."""
        # Determine bounds for this shape
        shape_h = max(o[0] for o in offsets)
        shape_w = max(o[1] for o in offsets)

        for r in range(8 - shape_h):
            for c in range(8 - shape_w):
                # Check this specific placement
                valid = True
                hit_overlap_count = 0

                coords = []
                for dr, dc in offsets:
                    curr_r, curr_c = r + dr, c + dc
                    cell_status = grid[curr_r][curr_c]

                    if cell_status == 'M':
                        valid = False
                        break
                    if cell_status == 'H' or cell_status == 'B':
                        hit_overlap_count += 1
                    coords.append((curr_r, curr_c))

                if valid:
                    # If it touches a hit, it becomes very probable
                    weight = base_weight + (hit_weight * hit_overlap_count)

                    # Add weight to all cells in this configuration
                    for cr, cc in coords:
                        heatmap[cr][cc] += weight

    def _get_best_shield_target(self, my_ships: list) -> list:
        """Returns the coordinate of the largest alive ship to shield."""
        alive_ships = []
        for ship in my_ships:
            coords = ship.get("coordinates", [])
            hits = ship.get("hits", [])
            # Only consider ships that are not sunk
            if len(hits) < len(coords):
                alive_ships.append(ship)

        if not alive_ships:
            return None

        # Protect the most damaged ship
        alive_ships.sort(key=lambda s: len(s.get("hits", [])), reverse=True)
        target_ship = alive_ships[0]

        if target_ship.get("coordinates"):
            return target_ship["coordinates"][0]
        return None


if __name__ == '__main__':
    run_bot(MyBattleshipBot)