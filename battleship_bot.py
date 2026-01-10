#!/usr/bin/env python3
"""
Code Clash Battleship Bot Challenge - CREATE UofT - Winter 2026

YOUR CUSTOM BATTLESHIP BOT STRATEGY
Override the strategy methods below to implement your bot.

Strategy:
1. Probability Density Model: Calculates a heatmap of all possible ship positions
   weighted by current hits (Hunt/Target algorithm).
2. Placement: Uses an inverse probability map to place ships in the least likely
   spots (edges/corners) to minimize enemy hit probability.
3. Abilities:
   - Hailstorm (HS): Used immediately if the enemy board is empty (Turn 1).
   - Shield (SD): Used if we take > 5 hits to prolong survival.
"""

import random
from battleship_api import BattleshipBotAPI, run_bot


class MyBattleshipBot(BattleshipBotAPI):

    def __init__(self):
        super().__init__()
        # Standard battleship sizes: 1x4, 1x3, 2x3 (treated as 6 cells? No, sizes are Dimensions), 1x2.
        # Note: The API says sizes are (1,4), (1,3), (2,3), (1,2).
        # We assume standard linear behavior for probability calculation mostly,
        # but 2x3 is a block. We will handle dimensions generically.
        self.ship_dimensions = [(1, 4), (1, 3), (2, 3), (1, 2)]

    def ability_selection(self) -> list:
        """Choose 2 abilities for the entire game."""
        # HS (Hailstorm) for early game damage
        # SD (Shield) for mid/late game survival
        return ["HS", "SD"]

    def place_ship_strategy(self, ship_name: str, game_state: dict) -> dict:
        """
        Place a ship on your board.
        Strategy: Place on the LEAST probable spots based on an empty board heatmap.
        This naturally pushes ships to corners and edges.
        """
        # 1. Calculate probability map for an empty board (N everywhere)
        # We create a dummy empty grid for this calculation
        empty_grid = [['N'] * 8 for _ in range(8)]
        heatmap = self._calculate_probability_map(empty_grid)

        placed_coords = self._get_placed_coordinates(game_state)

        # 2. Get all cells, sort them by probability (Ascending -> Lowest prob first)
        cells_with_prob = []
        for r in range(8):
            for c in range(8):
                cells_with_prob.append(((r, c), heatmap[r][c]))

        # Sort by probability score (lowest first)
        cells_with_prob.sort(key=lambda x: x[1])

        # 3. Try to place the ship starting from the best (lowest prob) cell
        for (r, c), prob in cells_with_prob:
            # Try both orientations
            for orientation in ['H', 'V']:
                ship_cells = self._get_ship_cells(ship_name, r, c, orientation)
                if ship_cells and self._is_valid_placement(ship_cells, placed_coords):
                    return {
                        "placement": {
                            "name": ship_name,
                            "cell": [r, c],
                            "direction": orientation
                        }
                    }

        # Fallback (should theoretically not be reached if board is open)
        return self._get_random_placement(ship_name, placed_coords)

    def combat_strategy(self, game_state: dict) -> dict:
        """Choose a combat move."""
        opponent_grid = self._get_opponent_grid(game_state)
        available_abilities = self._get_available_abilities(game_state)
        my_ships = self._get_own_ships(game_state)

        # --- ABILITY STRATEGY: HAILSTORM ---
        # If opponent grid is completely empty (all 'N'), use Hailstorm
        is_start_of_game = all(cell == 'N' for row in opponent_grid for cell in row)
        if is_start_of_game and "HS" in available_abilities:
            return {
                "combat": {
                    "cell": [0, 0],  # Cell ignored for HS
                    "ability": {"HS": {}}  # Payload for HS
                }
            }

        # --- ABILITY STRATEGY: SHIELD ---
        # If we have taken significant damage (>5 hits total), use Shield
        total_hits_taken = sum(len(ship.get("hits", [])) for ship in my_ships)
        if total_hits_taken > 5 and "SD" in available_abilities:
            # Find a ship that is alive but maybe damaged to protect
            target_ship_coord = self._get_best_shield_target(my_ships)
            if target_ship_coord:
                return {
                    "combat": {
                        "cell": target_ship_coord,  # Cell usually ignored, but good to set
                        "ability": {"SD": target_ship_coord}  # Shield needs a ship coordinate
                    }
                }

        # --- SHOOTING STRATEGY: PROBABILITY DENSITY ---
        # Calculate the heatmap based on current hits/misses
        heatmap = self._calculate_probability_map(opponent_grid)

        # Find the single highest probability cell that hasn't been shot
        best_cell = [0, 0]
        max_score = -1

        available_cells = self._get_available_cells(opponent_grid)

        # Map available cells to their heatmap scores
        candidates = []
        for cell in available_cells:
            r, c = cell
            score = heatmap[r][c]
            candidates.append((score, cell))

        # Shuffle equal scores to prevent deterministic loops
        random.shuffle(candidates)

        if candidates:
            # Pick the one with highest score
            best_cell = max(candidates, key=lambda x: x[0])[1]
        else:
            # Fallback if board is full (unlikely)
            best_cell = [random.randint(0, 7), random.randint(0, 7)]

        return {
            "combat": {
                "cell": best_cell,
                "ability": {"None": {}}
            }
        }

    # ------------------------------------------------------------------------
    # CUSTOM HELPER METHODS
    # ------------------------------------------------------------------------

    def _calculate_probability_map(self, grid: list) -> list:
        """
        Generates an 8x8 grid where each cell's value represents the probability
        of a ship occupying that cell.

        Logic:
        1. Iterate through every possible placement of every ship type.
        2. If a placement overlaps a Miss (M) or Block (B), it's invalid.
        3. If a placement fits:
           - Base score +1 per cell.
           - If it overlaps a Hit (H), Massive Bonus (Enter Target Mode).
        4. Accumulate scores on the heatmap.
        """
        heatmap = [[0.0] * 8 for _ in range(8)]

        # Weights
        BASE_WEIGHT = 1
        HIT_WEIGHT = 100  # High weight implies: "A ship definitely fits here and connects to a hit"

        # We assume all ships are potentially still in play to keep the heatmap robust.
        # This acts as a superposition of all possible remaining ships.
        for r_dim, c_dim in self.ship_dimensions:
            # Check horizontal placements of this shape
            # To handle NxM generic logic (including 2x3)
            # We treat the shape as a block of offsets

            # Generate offsets for this shape (Standard orientation)
            offsets = []
            for r in range(r_dim):
                for c in range(c_dim):
                    offsets.append((r, c))

            self._add_configuration_weights(grid, heatmap, offsets, BASE_WEIGHT, HIT_WEIGHT)

            # Generate offsets for rotated shape (if not square)
            if r_dim != c_dim:
                offsets_rotated = []
                for r in range(c_dim):  # Swap dims
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
        max_r = 7
        max_c = 7

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

                    if cell_status == 'M' or cell_status == 'B':
                        valid = False
                        break
                    if cell_status == 'H':
                        hit_overlap_count += 1
                    coords.append((curr_r, curr_c))

                if valid:
                    # Calculate weight for this configuration
                    # If it touches a hit, it becomes very probable
                    weight = base_weight + (hit_weight * hit_overlap_count)

                    # Add weight to all cells in this configuration
                    for cr, cc in coords:
                        heatmap[cr][cc] += weight

    def _get_best_shield_target(self, my_ships: list) -> list:
        """
        Returns the coordinate of a ship to shield.
        Prioritizes: Largest alive ship.
        """
        # Sort ships by size (descending), then by hits (descending)
        # We want to save big ships that are taking fire

        # Filter out sunken ships
        alive_ships = []
        for ship in my_ships:
            coords = ship.get("coordinates", [])
            hits = ship.get("hits", [])
            if len(hits) < len(coords):
                alive_ships.append(ship)

        if not alive_ships:
            return None

        # Strategy: Protect the largest ship that is currently alive
        # (Since size isn't explicitly in dict, infer from coord length)
        alive_ships.sort(key=lambda s: len(s.get("coordinates", [])), reverse=True)

        target_ship = alive_ships[0]

        # Return the first coordinate of that ship
        if target_ship.get("coordinates"):
            return target_ship["coordinates"][0]
        return None


if __name__ == '__main__':
    run_bot(MyBattleshipBot)