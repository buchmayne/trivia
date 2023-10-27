import random
from typing import Optional
from dataclasses import dataclass

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

def display_teams(teams: list) -> None:
    for team in teams:
        print(f"{team.name}: {', '.join(team.players)}\n")


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


if __name__ == "__main__":
    # Add participants and determine whether they have a partner
    players = [
    # 1-5
    Player("Mike T", True, "Tayler"),
    Player("Gerik", True, "Claire I"),
    Player("Dylan", True, "Erica"),
    Player("Andy", True, None),
    Player("Erica", False, "Dylan"),

	# 5-10
    Player("Jenna", False, None),
    Player("Tayler", False, "Mike T"),
    Player("Cole", True, "Sabrah"),
    Player("Connor", True, "Amanda"),
    Player("Hillary", False, "Father Doctor"),

	# 10-15
    Player("Howie", True, "Brittney"),
    Player("James", True, "Claire T"),
    Player("Kelsey", False, "Mike P"),
    Player("Father Doctor", True, "Hillary"),
    Player("Pilar", False, "Chris"),
	
	# 15-20
    Player("Brittney", False, "Howie"),
    Player("Chris", True, "Pilar"),
    Player("Emma", False, "Karson"),
    Player("Karson", True, "Emma"),
    Player("Kaylin", False, None),
 
    # 20-25
    Player("Mike P", True, "Kelsey"),

    # 26-30
#    Player("Sabrah", False, "Cole"),
#    Player("Amanda", False, "Connor"),
#    Player("Claire T", False, "James"),	
#    Player("Claire I", False, "Gerik"),
#    Player("Andrew", True, None),
    ]

    # Create teams and set max team size
    teams = [
        Team("Team 1", max_team_size=4),
        Team("Team 2", max_team_size=4),
        Team("Team 3", max_team_size=4),
        Team("Team 4", max_team_size=4),
        Team("Team 5", max_team_size=5),
    ]

    assigned_teams = assign_teams(players, teams)
    
    display_teams(assigned_teams)
