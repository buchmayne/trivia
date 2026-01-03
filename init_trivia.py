import random
from typing import Optional, List
from dataclasses import dataclass
import time
from datetime import date
import requests
import pandas as pd
import numpy as np
import gspread
from oauth2client.service_account import ServiceAccountCredentials


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


def assign_teams(players: List, teams: List) -> None:
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


def str_list_to_pretty_str(x) -> str:
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


## Connect to Google Sheets


def read_player_list_from_gsheet(csv_url: str, access_token: str) -> List:
    # Create authenticated session
    session = requests.Session()
    session.headers.update(
        {"Authorization": f"Bearer {access_token}", "Accept": "text/csv"}
    )
    response = session.get(csv_url)

    if response.status_code != 200:
        raise Exception(f"Failed to download CSV: {response.status_code}")

    player_dict = (
        pd.read_csv(pd.io.common.StringIO(response.content.decode("utf-8")))
        .assign(
            gender=lambda df_: df_["gender"].map({"F": False, "M": True}),
        )
        .replace({np.nan: None})
        .to_dict(orient="records")
    )
    return [Player(d["name"], d["gender"], d["partner"]) for d in player_dict]


def connect_to_gsheets() -> tuple:
    # Open the Google Sheet
    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive",
    ]
    creds = ServiceAccountCredentials.from_json_keyfile_name("gsheets_key.json", scope)
    client = gspread.authorize(creds)
    access_token = creds.get_access_token().access_token

    # need to pass in the url of the Players spreadsheet
    spreadsheet_url = f"https://docs.google.com/spreadsheets/d/1IuTrl0XtZTPC-WYG6VF8CacRIOcUyaP6l_xWN6GKavM/edit#gid=0"
    spreadsheet = client.open_by_url(spreadsheet_url)

    return spreadsheet, access_token


## Main


def main() -> None:
    """
    Example:
    make start
     player-sheet-name: Test
     number-of-teams: 6
     minimum-team-size: 4
    """
    print("=== Trivia Team Assignment ===\n")

    # Prompt for parameters
    player_sheet_name = input("Enter the player sheet name: ").strip()

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

    # connect to google sheets
    spreadsheet, access_token = connect_to_gsheets()

    players_list_spreadsheet = spreadsheet.worksheet(player_sheet_name)
    players_list_spreadsheet_id = players_list_spreadsheet.id

    # Construct the CSV export URL
    BASE_URL = "https://docs.google.com/spreadsheets/d/1IuTrl0XtZTPC-WYG6VF8CacRIOcUyaP6l_xWN6GKavM/export?format=csv&gid="
    csv_url = f"{BASE_URL}{players_list_spreadsheet_id}"

    # Download the CSV content from googlsheets
    players = read_player_list_from_gsheet(csv_url, access_token)

    # Create teams and set max team size
    teams = generate_teams_list(
        number_of_teams, minimum_team_size, number_of_players=len(players)
    )

    assigned_teams = assign_teams(players, teams)

    print("...All Players Succesfully Assigned to Teams\n\n\n")
    time.sleep(0.25)

    # Print team assignments for players
    display_teams(assigned_teams)

    # Set up game data
    game_df = create_game_df(assigned_teams)

    # Create new sheet
    sheet_name = f"trivia-{date.today()}"
    sheet = spreadsheet.add_worksheet(title=sheet_name, rows=100, cols=20)

    # Upload game data
    sheet.update([game_df.columns.values.tolist()] + game_df.values.tolist())

    return None


if __name__ == "__main__":
    main()
