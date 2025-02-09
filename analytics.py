import requests
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# FUNCTIONS
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
    creds = ServiceAccountCredentials.from_json_keyfile_name('gsheets_key.json', scope)
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
    

def aggregate_players(spreadsheet_url: str, players_list_spreadsheet_names: list) -> pd.DataFrame:
    return (
        pd.concat(
            [
                read_google_sheet(spreadsheet_url=spreadsheet_url, sheet_name=sheet) for sheet in players_list_spreadsheet_names
            ], 
            axis=0
        )
        .sort_values(by="name")
        [['name', 'gender']]
        .drop_duplicates()
        .reset_index(drop=True)
    )

def process_game_results(spreadsheet_url: str, game_sheet_name: str, game_potential_scoring: dict) -> pd.DataFrame:
    game_result = (
        read_google_sheet(spreadsheet_url=spreadsheet_url, sheet_name=game_sheet_name)
        .sort_values(by="Total", ascending=False)
        .reset_index(drop=True)
        .assign(
            game=game_sheet_name.replace('trivia-', ''),
            place=lambda df_: df_.index + 1,
            pct_rd1=lambda df_: df_['Round_1'] / game_potential_scoring[game_sheet_name]['Round_1'],
            pct_rd2=lambda df_: df_['Round_2'] / game_potential_scoring[game_sheet_name]['Round_2'],
            pct_final=lambda df_: df_['Final'] / game_potential_scoring[game_sheet_name]['Final_Round'],
            pct_total=lambda df_: df_['Total'] / game_potential_scoring[game_sheet_name]['Total'],
            normalized_total=lambda df_: df_['Total'] / df_['Total'].max(),
            zscore_total=lambda df_: (df_['Total'] - df_['Total'].mean()) / df_['Total'].std()
        )
        .assign(game_date=lambda df_: pd.to_datetime(df_['game'], format='%Y-%m-%d'))
        .drop(['Team_Name', 'game'], axis=1)
    )
    return game_result


if __name__ == "__main__":
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

    players_list_spreadsheet_names = [
        "Players-04-12-24",
        "Players-01-21-25",
    ]

    game_list_spreadsheet_names = [
        "trivia-2024-04-12",
        "trivia-2025-01-21",
    ]

    game_potential_scoring = {
        "trivia-2024-04-12": {
            "Round_1": 69,
            "Round_2": 53,
            "Final_Round": 40,
            "Total": 162
        },
        "trivia-2025-01-21": {
            "Round_1": 51,
            "Round_2": 81,
            "Final_Round": 14,
            "Total": 146
        },
    }

    # Get players list and all game results
    players = aggregate_players(spreadsheet_url, players_list_spreadsheet_names)

    game_results = (
        pd.concat(
            [
                process_game_results(spreadsheet_url=spreadsheet_url, game_sheet_name=sheet, game_potential_scoring=game_potential_scoring) for sheet in game_list_spreadsheet_names
            ], 
            axis=0
        )
    )

    # Create players historical stats
    historic_players_stats = (
        pd.concat([
            (
                game_results.loc[lambda df_: df_['players'].str.contains(player)]
                .reset_index(drop=True)
                .assign(player=player)
                .rename(columns={'players': 'team'})
                .sort_values(by=['player', 'game_date'], ascending=[True, True])
                .assign(games_played=lambda df_: df_.index + 1)
            ) for player in players['name']
        ], axis=0)
    )

    list_of_players_who_have_played_multiple_games = (
        historic_players_stats.loc[lambda df_: df_['games_played'] > 1, 'player'].drop_duplicates().tolist()
    )

    print(
        historic_players_stats
        .loc[lambda df_: df_['player'].isin(list_of_players_who_have_played_multiple_games)]
        .loc[lambda df_: df_['player'] != 'Cam']
        .drop(['team', 'Round_1', 'Round_2', 'Final', 'game_date', 'games_played'], axis=1)
        .groupby('player')
        .mean()
        .sort_values('zscore_total', ascending=False)
    )
    