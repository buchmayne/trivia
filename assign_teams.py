import sys
import ast
import random

def determine_team_sizes(teams, n_players, team_size):
    for team in teams.keys():
        if n_players > 0:
            if 'team_size' not in teams[team].keys():
                teams[team]['team_size'] = team_size
                n_players -= team_size
            elif teams[team]['team_size'] == team_size:
                teams[team]['team_size'] += 1
                n_players -= 1
    # allocate remainder if remainder exists
    for team in teams.keys():
        if n_players > 0:
            if 'team_size' not in teams[team].keys():
                teams[team]['team_size'] = team_size
                n_players -= team_size
            elif teams[team]['team_size'] == team_size:
                teams[team]['team_size'] += 1
                n_players -= 1
    return teams


def get_players_partner(partners, player):
    partner_pair = [pair for pair in partners if player in pair][0]
    partner = [person for person in partner_pair if person is not player][0]
    return partner


def allocate_players_to_teams(players, teams, partners):
    for player in players:
        on_a_team = False
        is_a_partner = any([player in pair for pair in partners])
        for team in teams:
            if not on_a_team:
                # check whether team has space
                if len(teams[team]['team_members']) < teams[team]['team_size']:    
                    if not is_a_partner:
                        teams[team]['team_members'].append(player)
                        on_a_team = True
                    else:
                        their_partner = get_players_partner(partners, player)
                        if their_partner in teams[team]['team_members']:
                            pass
                        else:
                            teams[team]['team_members'].append(player)
                            on_a_team = True
    return teams
                    

def print_teams(teams):
    for team in teams:
        print("\n")
        print(f"Team {team}:")
        for player in teams[team]['team_members']:
            print(player)


def assign_teams(n_teams, partners, singles):
    # create list of players
    players = [p1 for p2 in partners for p1 in p2] + singles
    # randomize allocation
    random.shuffle(players)
    # determine minimum team size
    team_size = round(len(players) / n_teams).__floor__()
    # create team data structure
    teams = {i + 1: {'team_members': []} for i in range(n_teams)}
    # get number of total players
    n_players = len(players)
    # determine team sizes
    teams = determine_team_sizes(teams, n_players, team_size)
    # aassign teams
    teams = allocate_players_to_teams(players, teams, partners)
    
    print_teams(teams)

if __name__ == "__main__":
    # partners = [
    #     ('Mike Turnell', 'Tayler Thomas'),
    #     ('Mike Park', 'Kelsey Park'),
    #     ('Gerik Illo', 'Claire Illo'),
    #     ('Howie Rabin', 'Brittany Rabin'),
    #     ('Alex Melcher', 'Hillary Melcher'),
    #     ('Dylan Scandi', 'Erica Bochi'),
    # ]

    # singles = [
    #     'Andy Lipski', 
    #     'Kaylin Youn', 
    #     'Jenna Carlson', 
    # ]

    # Access the command-line arguments
    n_teams = sys.argv[1]
    partners = ast.literal_eval(sys.argv[2])
    singles = ast.literal_eval(sys.argv[3])

    assign_teams(n_teams=4, partners=partners, singles=singles)
