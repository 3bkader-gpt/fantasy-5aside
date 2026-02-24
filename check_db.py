from app.database import SessionLocal, engine
from app.models.models import League

print("Engine URL:", engine.url)
db = SessionLocal()
leagues = db.query(League).all()
print('Leagues in DB:')
for l in leagues: 
    print(f'- {l.name} ({l.slug})')
db.close()
