"""
Offline variant of init_trivia.py for assigning teams with no internet access
(e.g. hosting trivia while camping).

Reads players from a local CSV instead of a Google Sheet, and writes the
resulting team/scoring assignments to a local CSV instead of uploading to a
live Google Sheet. Once back online, copy the output CSV's contents into the
real Google Sheet by hand.

This file intentionally duplicates the Player/Team/assignment/reveal logic
from init_trivia.py rather than sharing a module with it, to keep this a
simple, standalone, throwaway offline tool.

This is a personal, dev-only tool. It is not used in production or CI.

Usage:
    uv run python init_trivia_offline.py
    (or: make start-offline)
"""

import random
from typing import Optional, List
from dataclasses import dataclass
import time
from datetime import date

import pandas as pd
import numpy as np

## Define Player and Team Functionality


@dataclass
class Player:
    name: str
    male: bool
    partner: Optional[str]


class Team:
    def __init__(self, name: str, max_team_size: int, players=None):
        self.name = name
        self.max_team_size = max_team_size
        if players is not None:
            self.players = list(players)
        else:
            self.players = []

    def add_player(self, player):
        return self.players.append(player)

    def __iter__(self):
        return iter(self.players)

    def __str__(self):
        return str([str(player) for player in self.players])


## Team Assignment


def sort_players_by_sex(players: List) -> dict:
    men = []
    women = []
    for player in players:
        if player.male:
            men.append(player)
        else:
            women.append(player)

    return {"men": men, "women": women}


def assign_teams(players: List, teams: List) -> List:
    # try to balance teams by sex
    sorted_by_sex = sort_players_by_sex(players)
    men = sorted_by_sex["men"]
    women = sorted_by_sex["women"]

    # shuffle male and female player pools
    random.shuffle(men)
    random.shuffle(women)

    # assign teams balanced by sex, and avoiding partners on the same team
    selected_players = []
    select_male = True

    while len(selected_players) < len(players):
        if select_male:
            if len(men) > 0:
                chosen_player = random.choice(men)
                for team in teams:
                    if len(team.players) < team.max_team_size:
                        assigned_players = [p for t in teams for p in t.players]
                        if chosen_player.name not in assigned_players:
                            if (
                                chosen_player.partner is None
                                or chosen_player.partner not in team.players
                            ):
                                team.add_player(chosen_player.name)
                                men = [
                                    male_player
                                    for male_player in men
                                    if male_player.name != chosen_player.name
                                ]
                                selected_players.append(chosen_player)
                                select_male = False
                            else:
                                pass
            else:
                select_male = False
        else:
            if len(women) > 0:
                chosen_player = random.choice(women)
                for team in teams:
                    if len(team.players) < team.max_team_size:
                        assigned_players = [p for t in teams for p in t.players]
                        if chosen_player.name not in assigned_players:
                            if (
                                chosen_player.partner is None
                                or chosen_player.partner not in team.players
                            ):
                                team.add_player(chosen_player.name)
                                women = [
                                    female_player
                                    for female_player in women
                                    if female_player.name != chosen_player.name
                                ]
                                selected_players.append(chosen_player)
                                select_male = True
                            else:
                                pass
            else:
                select_male = True

    return teams


def generate_teams_list(
    number_of_teams: int, min_team_size: int, number_of_players: int
) -> List:
    teams = []
    for i in range(number_of_teams):
        teams.append(Team(f"Team {i+1}", max_team_size=min_team_size))
    # assign remainder of players to teams
    remaining_players_to_be_assigned = number_of_players - (
        number_of_teams * min_team_size
    )
    if remaining_players_to_be_assigned > 0:
        for i in range(remaining_players_to_be_assigned):
            teams[i].max_team_size = min_team_size + 1

    return teams


## Reveal Results of Assignment


def dramatic_print(string: str) -> None:
    for char in string:
        print(char, end="", flush=True)
        time.sleep(0.05)


def str_list_to_pretty_str(x: List) -> str:
    return str(x).replace("'", "").replace("[", "").replace("]", "")


def spotlight_reveal(team_name: str, player: str, player_num: int) -> None:
    """Create spotlight effect for each player."""

    if player_num == 1:
        print(f"\n╔{'═'*48}╗")
        print(f"║  {team_name:^44}  ║")
        print(f"╚{'═'*48}╝\n")
        time.sleep(0.3)

    # Countdown effect
    print("  ", end="", flush=True)
    for i in range(3, 0, -1):
        print(f"{i}...", end="", flush=True)
        time.sleep(0.3)

    # Reveal with emphasis
    print(f"\r  ⚡ Player {player_num}: {player}     ")
    time.sleep(0.5)


def display_teams(teams: List) -> None:
    """Spotlight-style dramatic reveal."""
    print("\n" + "█" * 50)
    print("  📣📜📣  TEAM REVEAL CEREMONY  📣📜📣")
    print("█" * 50)
    time.sleep(1)

    for team in teams:
        players = str_list_to_pretty_str(team).split(", ")

        for i, player in enumerate(players, 1):
            spotlight_reveal(team.name, player, i)

        print()
        time.sleep(0.8)


## Create Data for Export


def create_game_df(teams: List) -> pd.DataFrame:
    team_dict = {
        team.name: {
            "players": str_list_to_pretty_str([player for player in team]),
            "Round_1": 0,
            "Round_2": 0,
            "Final:": 0,
            "Total": 0,
        }
        for team in teams
    }
    # convert to dataframe
    df = (
        pd.DataFrame.from_dict(team_dict, orient="index")
        .reset_index()
        .rename(columns={"index": "Team_Name"})
    )

    return df


## Read Players from a Local CSV (offline replacement for Google Sheets)


def read_player_list_from_csv(csv_path: str) -> List:
    """
    Read players from a local CSV with columns: name, gender, partner
    (same columns/semantics as the Google Sheet used by init_trivia.py:
    gender is "M"/"F", partner may be blank).
    """
    player_dict = (
        pd.read_csv(csv_path)
        .assign(
            gender=lambda df_: df_["gender"].map({"F": False, "M": True}),
        )
        .replace({np.nan: None})
        .to_dict(orient="records")
    )
    return [Player(d["name"], d["gender"], d["partner"]) for d in player_dict]


## Main


def main() -> None:
    """
    Example:
    make start-offline
     players csv path: players.csv
     number-of-teams: 6
     minimum-team-size: 4
    """
    print("=== Trivia Team Assignment (Offline) ===\n")

    # Prompt for parameters
    players_csv_path = input(
        "Enter the path to the players CSV (columns: name, gender, partner): "
    ).strip()

    while True:
        try:
            number_of_teams = int(input("Enter number of teams: ").strip())
            break
        except ValueError:
            print("Please enter a valid integer for number of teams.")

    while True:
        try:
            minimum_team_size = int(input("Enter minimum team size: ").strip())
            break
        except ValueError:
            print("Please enter a valid integer for minimum team size.")

    print("...Initiating Team Assignment\n")
    time.sleep(0.25)

    # Read the player list from a local CSV instead of Google Sheets
    players = read_player_list_from_csv(players_csv_path)

    # Create teams and set max team size
    teams = generate_teams_list(
        number_of_teams, minimum_team_size, number_of_players=len(players)
    )

    assigned_teams = assign_teams(players, teams)

    print("...All Players Succesfully Assigned to Teams\n\n\n")
    time.sleep(0.25)

    # Print dramatic reveal
    display_teams(assigned_teams)

    # Set up game data
    game_df = create_game_df(assigned_teams)

    # Print compact list of each team and the assigned players
    for team in assigned_teams:
        print(f"{team.name}: {str_list_to_pretty_str(team.players)}")

    # Write results to a local CSV instead of uploading to Google Sheets.
    # Copy this into the real Google Sheet by hand once back online.
    output_path = f"trivia-{date.today()}.csv"
    game_df.to_csv(output_path, index=False)
    print(f"\nTeam assignments written to {output_path}")

    return None


if __name__ == "__main__":
    main()
