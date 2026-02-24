import os
from app.database import SessionLocal, engine, Base
from app.models.models import Player

# Ensure the data directory exists
if not os.path.exists("./data"):
    os.makedirs("./data")

def seed_data():
    Base.metadata.create_all(bind=engine)
    
    db = SessionLocal()
    
    players = [
        "محمد عمر", "شادي مهدي", "يوسف مصطفى", "احمد شريف", "بلال مجدي", 
        "محمد طه", "عمرو محمد", "احمد عبد التواب", "عبد الرحمن أيمن", "محمد سيد"
    ]
    
    # Create a default league if none exists
    from app.models.models import League
    from app.core import security
    default_league = db.query(League).filter(League.slug == "default").first()
    if not default_league:
        default_league = League(name="Default League", slug="default", admin_password=security.get_password_hash("admin"))
        db.add(default_league)
        db.commit()
        db.refresh(default_league)

    for player_name in players:
        existing_player = db.query(Player).filter(Player.name == player_name, Player.league_id == default_league.id).first()
        if not existing_player:
            player = Player(name=player_name, league_id=default_league.id)
            db.add(player)
    
    db.commit()
    db.close()
    print("Database initialized and players seeded successfully.")

if __name__ == "__main__":
    seed_data()
