import random
from typing import Optional
from dataclasses import dataclass
from time import sleep

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

    return {'men': men, 'women': women}


def assign_teams(players: list, teams: list) -> None:
    # try to balance teams by sex
    sorted_by_sex = sort_players_by_sex(players)
    men = sorted_by_sex['men']
    women = sorted_by_sex['women']
    
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
                            if chosen_player.partner is None or chosen_player.partner not in team.players:
                                team.add_player(chosen_player.name)
                                men = [male_player for male_player in men if male_player.name != chosen_player.name]
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
                            if chosen_player.partner is None or chosen_player.partner not in team.players:
                                team.add_player(chosen_player.name)
                                women = [female_player for female_player in women if female_player.name != chosen_player.name]
                                selected_players.append(chosen_player)
                                select_male = True
                            else:
                                pass
            else:
                select_male = True
    

    return teams

def display_teams(teams: list) -> None:
    for team in teams:
        team_visual = f"{team.name}: "
        for player in team.players:
            team_visual = team_visual + f" {player},"
            sleep(1)
            print(team_visual)


if __name__ == "__main__":
    print("Assigning Teams\n")
    sleep(1)
    
    # Add participants and determine whether they have a partner
    players = [
    # 1-5
    Player("Brittney Malhoit", False, "Howie Rabin"),
    Player("Dylan Scandalios", True, "Erica Scandalios"),
    Player("Hillary Melcher", False, "Alex Melcher"),
    Player("Howie Rabin", True, "Brittney Malhoit"),
    Player("Jenna Carlson", False, None),


	# 5-10
    Player("Kaylin Youn", False, None),
    Player("Erica Scandalios", False, "Dylan Scandalios"),
    Player("Alex Melcher", True, "Hillary Melcher"),
    Player("Colby", True, None),
    Player("Steven", True, None),

	# 10-15
    Player("Pilar Hoch", False, "Chris Hoch"),
    Player("Chris Hoch", True, "Pilar Hoch"),
    Player("Andrew Dang", True, None),
    Player("Zo", True, None),
    Player("Gabs", False, None),

	
	# 15-20
    Player("Hope", False, None),
    Player("Michael Park", True, "Kelsey Park"),
    Player("Josefa", False, "Sam"),
    Player("Sam", True, "Josefa"),
    Player("Lauren", False, None),
    

    # 20-25
    Player("James Higgins", True, "Claire Higgins"),
    # Maybe...
    
    # Player("Olivia Gonzales", False, "John"),
    # Player("John", True, "Olivia Gonzales"),
    # Player("Elliott Damman", False, "Cody Damman"),
    # Player("Jamie", False, None),
    # # 25-30
    # Player("Claire Illo", False, "Gerik Illo"),
    # Player("Gerik Illo", True, "Claire Illo"),
    # Player("Cody Damman", True, "Elliot Damman"),
    # Player("Shelby Hawkinson", False, None),

    ]

    # Create teams and set max team size
    teams = [
        Team("Team 1", max_team_size=5),
        Team("Team 2", max_team_size=4),
        Team("Team 3", max_team_size=4),
        Team("Team 4", max_team_size=4),
        Team("Team 5", max_team_size=4),
    ]

    assigned_teams = assign_teams(players, teams)

    print("Teams Assigned\n")
    sleep(1)
    
    display_teams(assigned_teams)
