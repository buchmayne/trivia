import os
import sys
from pathlib import Path

# Add the project root directory to the Python path
project_root = Path(__file__).resolve().parent.parent
sys.path.append(str(project_root))

# Set up Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'pub_trivia.settings')

import django
django.setup()

from django.conf import settings
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# Metadata needed to calculate player stats
spreadsheet_url = "https://docs.google.com/spreadsheets/d/1IuTrl0XtZTPC-WYG6VF8CacRIOcUyaP6l_xWN6GKavM/edit#gid=0"

trivia_metadata = {
        "trivia-2024-04-12": {
            "player_list_sheet_name": "Players-04-12-24",
            "game_data": {
                "Round_1": 69,
                "Round_2": 53,
                "Final_Round": 40,
                "Total": 162
            }
        },
        "trivia-2025-01-21": {
            "player_list_sheet_name": "Players-01-21-25",
            "game_data": {
                "Round_1": 51,
                "Round_2": 81,
                "Final_Round": 14,
                "Total": 146
            }
        },
    }


# Functions
def get_credentials_path():
    """Get the path to credentials file whether running standalone or in Django"""
    try:
        # Try Django settings first
        base_dir = settings.BASE_DIR
    except:
        # Fallback to calculating path relative to this file
        base_dir = Path(__file__).resolve().parent.parent
    
    return os.path.join(base_dir, 'gsheets_key.json')

def read_google_sheet(spreadsheet_url: str, sheet_name: str) -> pd.DataFrame:
    """
    Read a Google Sheet into a pandas DataFrame
    
    Parameters:
    -----------
    spreadsheet_url : str
        The full URL of the Google Spreadsheet
    sheet_name : str
        The name of the specific worksheet to read
        
    Returns:
    --------
    pd.DataFrame
        DataFrame containing the sheet data
    """
    # Set up Google Sheets authentication
    scope = [
        'https://spreadsheets.google.com/feeds',
        'https://www.googleapis.com/auth/drive'
    ]
    
    credentials_path = get_credentials_path()
    
    creds = ServiceAccountCredentials.from_json_keyfile_name(credentials_path, scope)
    client = gspread.authorize(creds)
    
    try:
        # Open the spreadsheet and worksheet
        spreadsheet = client.open_by_url(spreadsheet_url)
        worksheet = spreadsheet.worksheet(sheet_name)
        
        # Get all values from the worksheet
        data = worksheet.get_all_records()
        
        # Convert to DataFrame
        df = pd.DataFrame(data)
        
        return df
        
    except gspread.exceptions.SpreadsheetNotFound:
        raise ValueError(f"Could not find spreadsheet at URL: {spreadsheet_url}")
    except gspread.exceptions.WorksheetNotFound:
        raise ValueError(f"Could not find worksheet named: {sheet_name}")
    except Exception as e:
        raise Exception(f"Error reading Google Sheet: {str(e)}")
    

def get_players_list(spreadsheet_url: str, trivia_metadata: dict) -> list:
    """From google sheets that contain the list of players, combine them into a single unique list"""
    players_list_sheet_names = [trivia_metadata[game]['player_list_sheet_name'] for game in trivia_metadata]
    return (
        pd.concat(
            [
                read_google_sheet(
                    spreadsheet_url=spreadsheet_url,
                    sheet_name=sheet
                ) for sheet in players_list_sheet_names
            ], 
            axis=0
        )
        .sort_values(by="name")
        [['name', 'gender']]
        .drop_duplicates()
        .reset_index(drop=True)
        ['name']
        .tolist()
    )

def process_game_results(spreadsheet_url: str, game_sheet_name: str, game_data: dict) -> pd.DataFrame:
    """For a given trivia game, process the results and calculate stats"""
    game_result = (
        read_google_sheet(spreadsheet_url=spreadsheet_url, sheet_name=game_sheet_name)
        .sort_values(by="Total", ascending=False)
        .reset_index(drop=True)
        .assign(
            game=game_sheet_name.replace('trivia-', ''),
            place=lambda df_: df_.index + 1,
            pct_rd1=lambda df_: df_['Round_1'] / game_data['Round_1'],
            pct_rd2=lambda df_: df_['Round_2'] / game_data['Round_2'],
            pct_final=lambda df_: df_['Final'] / game_data['Final_Round'],
            pct_total=lambda df_: df_['Total'] / game_data['Total'],
            normalized_total=lambda df_: df_['Total'] / df_['Total'].max(),
            zscore_total=lambda df_: (df_['Total'] - df_['Total'].mean()) / df_['Total'].std(),
            winner=lambda df_: df_['place'] == 1
        )
        .assign(game_date=lambda df_: pd.to_datetime(df_['game'], format='%Y-%m-%d'))
        .drop(['Team_Name', 'game'], axis=1)
    )
    return game_result

def exact_player_match(df, player_name):
    """Match player only if their exact name appears in the players list"""
    return df.loc[
        df['players'].apply(
            lambda x: player_name in [name.strip() for name in x.split(',')]
        )
    ]

def get_game_results(spreadsheet_url: str, trivia_metadata: dict) -> pd.DataFrame:
    """Create game results for all games"""
    game_list_spreadsheet_names = trivia_metadata.keys()
    
    return (
        pd.concat(
            [
                process_game_results(
                    spreadsheet_url=spreadsheet_url,
                    game_sheet_name=sheet,
                    game_data=trivia_metadata[sheet]['game_data']
                ) for sheet in game_list_spreadsheet_names
            ], 
            axis=0
        )
    )

def get_player_stats(game_results: pd.DataFrame, players: list) -> pd.DataFrame:
        """Create player level statistics for all games"""
        return (
            pd.concat([
                (
                    game_results
                    .pipe(exact_player_match, player)
                    .reset_index(drop=True)
                    .assign(player=player)
                    .rename(columns={'players': 'team'})
                    .sort_values(by=['player', 'game_date'], ascending=[True, True])
                    .assign(games_played=lambda df_: df_.index + 1)
                ) for player in players
            ], axis=0)
        )

def calculate_player_performance(players_stats: pd.DataFrame) -> pd.DataFrame:
    """Calculate player performance metrics averaged over all games"""
    return (
        players_stats
        [[
            "player",
            "place",
            "winner",
            "Total",
            "pct_total",
            "normalized_total",
            "zscore_total",
            "pct_rd1",
            "pct_rd2",
            "pct_final"
        ]]
        .groupby('player', as_index=False)
        .agg(
            avg_final_place=("place", "mean"),
            total_wins=("winner", "sum"),
            avg_zscore_total_points=("zscore_total", "mean"),
            avg_total_points=("Total", "mean"),
            avg_pct_total_points=("pct_total", "mean"),
            avg_normalized_total_points=("normalized_total", "mean"),
            avg_pct_rd1_points=("pct_rd1", "mean"),
            avg_pct_rd2_points=("pct_rd2", "mean"),
            avg_pct_final_rd_points=("pct_final", "mean"),
            games_played=("player", "count"),
        )
        .sort_values(['avg_final_place', 'total_wins', 'avg_zscore_total_points'], ascending=[True, True, False])
        
    )

if __name__ == "__main__":
    # Get players list and all game results
    players = get_players_list(spreadsheet_url, trivia_metadata)
    
    # Get stats from all games with custom metrics
    game_results = get_game_results(spreadsheet_url, trivia_metadata) # included in analytics view

    # Create players historical stats
    players_stats = get_player_stats(game_results, players)

    # Get aggregated player performance
    career_stats = calculate_player_performance(players_stats) # included in analytics view