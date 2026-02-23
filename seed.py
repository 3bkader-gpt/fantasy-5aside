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
    
    for player_name in players:
        existing_player = db.query(Player).filter(Player.name == player_name).first()
        if not existing_player:
            player = Player(name=player_name)
            db.add(player)
    
    db.commit()
    db.close()
    print("Database initialized and players seeded successfully.")

if __name__ == "__main__":
    seed_data()
