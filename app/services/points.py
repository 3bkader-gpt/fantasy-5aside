def calculate_player_points(
    goals: int, 
    assists: int, 
    is_winner: bool, 
    is_gk: bool,
    clean_sheet: bool,
    mvp: bool,
    saves: int,
    goals_conceded: int,
    is_captain: bool = False
) -> int:
    """
    Calculate points based on advanced 5-a-side rules.
    If is_captain is True, the total points are doubled.
    """
    points = 1  # Participation points
    
    # Point values
    goal_value = 4 if is_gk else 2
    assist_value = 2 if is_gk else 1
    
    points += goals * goal_value
    points += assists * assist_value
    
    if is_winner:
        points += 2
        
    if mvp:
        points += 3
        
    # Clean Sheet: +5 if GK, +2 if Player
    if clean_sheet:
        if is_gk:
            points += 5
        else:
            points += 2
            
    # Saves: +1 per 3 saves
    points += (saves // 3)
    
    # Goals Conceded Penalty: -1 per 4 goals
    points -= (goals_conceded // 4)

    # Captain Double points
    if is_captain:
        points *= 2
        
    return points
