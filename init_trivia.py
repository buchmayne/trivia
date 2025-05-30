import random
from typing import Optional
from dataclasses import dataclass
from time import sleep
from datetime import date
import requests
import pandas as pd
import numpy as np
import gspread
from oauth2client.service_account import ServiceAccountCredentials


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


def sort_players_by_sex(players: list) -> dict:
    men = []
    women = []
    for player in players:
        if player.male:
            men.append(player)
        else:
            women.append(player)

    return {"men": men, "women": women}


def assign_teams(players: list, teams: list) -> None:
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


def dramatic_print(string: str) -> None:
    for char in string:
        print(char, end="", flush=True)
        sleep(0.05)


def str_list_to_pretty_str(x) -> str:
    return str(x).replace("'", "").replace("[", "").replace("]", "")


def display_teams(teams: list) -> None:
    for team in teams:
        team_name = team.name
        players = str_list_to_pretty_str(team)
        to_display = f"{team_name}: {players}"

        dramatic_print(to_display)
        print("\n")


def create_game_df(teams: list) -> pd.DataFrame:
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


def read_player_list_from_gsheet(csv_url: str, access_token: str) -> list:
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


if __name__ == "__main__":
    print("Assigning Teams\n")
    sleep(0.5)

    # Open the Google Sheet
    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive",
    ]
    creds = ServiceAccountCredentials.from_json_keyfile_name("gsheets_key.json", scope)
    client = gspread.authorize(creds)
    access_token = creds.get_access_token().access_token

    spreadsheet_url = f"https://docs.google.com/spreadsheets/d/1IuTrl0XtZTPC-WYG6VF8CacRIOcUyaP6l_xWN6GKavM/edit#gid=0"
    spreadsheet = client.open_by_url(spreadsheet_url)

    players_list_spreadsheet_name = "Players-01-21-25"
    players_list_spreadsheet = spreadsheet.worksheet(players_list_spreadsheet_name)
    players_list_spreadsheet_id = players_list_spreadsheet.id

    # Construct the CSV export URL
    csv_url = f"https://docs.google.com/spreadsheets/d/1IuTrl0XtZTPC-WYG6VF8CacRIOcUyaP6l_xWN6GKavM/export?format=csv&gid={players_list_spreadsheet_id}"

    # Download the CSV content from googlsheets
    players = read_player_list_from_gsheet(csv_url, access_token)

    print(players)

    # Create teams and set max team size
    teams = [
        Team("Team 1", max_team_size=4),
        Team("Team 2", max_team_size=4),
        Team("Team 3", max_team_size=4),
        Team("Team 4", max_team_size=4),
        Team("Team 5", max_team_size=5),
        Team("Team 6", max_team_size=5),
    ]

    assigned_teams = assign_teams(players, teams)

    print("Teams Assigned\n")
    sleep(0.5)

    # Print team assignments for players
    display_teams(assigned_teams)

    # Set up game data
    game_df = create_game_df(assigned_teams)

    # Create new sheet
    sheet_name = f"trivia-{date.today()}"
    sheet = spreadsheet.add_worksheet(title=sheet_name, rows=100, cols=20)

    # Upload game data
    sheet.update([game_df.columns.values.tolist()] + game_df.values.tolist())
