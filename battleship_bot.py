#!/usr/bin/env python3
"""
Code Clash Battleship Bot Challenge - CREATE UofT - Winter 2026

YOUR CUSTOM BATTLESHIP BOT STRATEGY
Override the strategy methods below to implement your bot.

Strategy:
1. Probability Density Model: Calculates a heatmap of all possible ship positions
   weighted by current hits (Hunt/Target algorithm).
2. Placement:
   - Uses an inverse probability map to place ships in the least likely spots (edges/corners).
   - Enforces a "Spacing Constraint": No two ships can touch (1-cell gap) to prevent clustering.
3. Abilities:
   - Hailstorm (HS): Used immediately if the enemy board is empty (Turn 1).
   - Shield (SD): Used if we take > 5 hits to prolong survival.
"""

import random
from battleship_api import BattleshipBotAPI, run_bot


class MyBattleshipBot(BattleshipBotAPI):

    def __init__(self):
        super().__init__()
        # Dimensions derived from battleship_api.SHIP_SIZES
        # Used for generic probability calculations
        self.ship_dimensions = [(1, 4), (1, 3), (2, 3), (1, 2)]

    def ability_selection(self) -> list:
        """Choose 2 abilities for the entire game."""
        # HS (Hailstorm) for early game damage
        # SD (Shield) for mid/late game survival
        return ["HS", "SD"]

    def place_ship_strategy(self, ship_name: str, game_state: dict) -> dict:
        """
        Place a ship on your board.
        Strategy: Place on LEAST probable spots + Ensure no adjacency to other ships.
        """
        # 1. Calculate probability map for an empty board (N everywhere)
        # This highlights the center as "high prob" and corners as "low prob"
        empty_grid = [['N'] * 8 for _ in range(8)]
        heatmap = self._calculate_probability_map(empty_grid)

        placed_coords = self._get_placed_coordinates(game_state)

        # 2. Calculate "Forbidden Buffer": Cells adjacent to existing ships
        # This ensures we don't place ships touching each other
        forbidden_buffer = set()
        for r, c in placed_coords:
            for dr, dc in [(0, 1), (0, -1), (1, 0), (-1, 0)]:
                nr, nc = r + dr, c + dc
                if 0 <= nr < 8 and 0 <= nc < 8:
                    forbidden_buffer.add((nr, nc))

        # 3. Sort board cells by probability (Ascending -> place in low prob areas first)
        cells_with_prob = []
        for r in range(8):
            for c in range(8):
                cells_with_prob.append(((r, c), heatmap[r][c]))

        cells_with_prob.sort(key=lambda x: x[1])

        # 4. Attempt Strict Placement (No Overlap + No Adjacency)
        for (r, c), prob in cells_with_prob:
            for orientation in ['H', 'V']:
                ship_cells = self._get_ship_cells(ship_name, r, c, orientation)

                # Skip invalid bounds
                if not ship_cells:
                    continue

                # Check 1: Must not overlap existing ships
                if not self._is_valid_placement(ship_cells, placed_coords):
                    continue

                # Check 2: Must not touch existing ships (Buffer check)
                if any(cell in forbidden_buffer for cell in ship_cells):
                    continue

                return {
                    "placement": {
                        "name": ship_name,
                        "cell": [r, c],
                        "direction": orientation
                    }
                }

        # 5. Fallback: Relaxed Placement (Allow Adjacency if necessary)
        # If the board is too crowded for gaps, just find any valid spot
        for (r, c), prob in cells_with_prob:
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

        # 6. Final Fallback (Should typically not be reached)
        return self._get_random_placement(ship_name, placed_coords)

    def combat_strategy(self, game_state: dict) -> dict:
        """Choose a combat move based on Probability Density."""
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
                    "ability": {"HS": {}}
                }
            }

        # --- ABILITY STRATEGY: SHIELD ---
        # If we have taken significant damage (>5 hits total), use Shield
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

        # --- SHOOTING STRATEGY: PROBABILITY DENSITY ---
        # Calculate the heatmap based on current hits/misses
        heatmap = self._calculate_probability_map(opponent_grid)

        available_cells = self._get_available_cells(opponent_grid)

        # Map available cells to their heatmap scores
        candidates = []
        for cell in available_cells:
            r, c = cell
            score = heatmap[r][c]
            candidates.append((score, cell))

        # Shuffle equal scores to prevent deterministic loops on zero-info turns
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
    # CUSTOM HELPER METHODS
    # ------------------------------------------------------------------------

    def _calculate_probability_map(self, grid: list) -> list:
        """
        Generates an 8x8 grid where each cell's value represents the probability
        of a ship occupying that cell.
        """
        heatmap = [[0.0] * 8 for _ in range(8)]

        # Weights
        BASE_WEIGHT = 1
        HIT_WEIGHT = 100  # Heavily weight alignments that overlap 'H'

        # Superposition of all ship types
        for r_dim, c_dim in self.ship_dimensions:

            # Generate offsets for this shape (Standard)
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

        # Protect the largest ship
        alive_ships.sort(key=lambda s: len(s.get("coordinates", [])), reverse=True)
        target_ship = alive_ships[0]

        if target_ship.get("coordinates"):
            return target_ship["coordinates"][0]
        return None


if __name__ == '__main__':
    run_bot(MyBattleshipBot)