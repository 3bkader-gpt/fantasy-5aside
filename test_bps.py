from app.services.points import calculate_player_points

def main():
    pts = calculate_player_points(
        goals=2,
        assists=1,
        is_winner=True,
        is_draw=False,
        is_gk=False,
        clean_sheet=False,
        saves=0,
        goals_conceded=0,
    )
    print("Player points:", pts)

if __name__ == "__main__":
    main()