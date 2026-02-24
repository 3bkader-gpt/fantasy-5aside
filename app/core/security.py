from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        # Check if the stored password is an old plaintext password (fallback)
        # Bcrypt hashes always start with $2a$, $2b$, or $2y$.
        if not hashed_password.startswith("$2"):
            return plain_password == hashed_password
        return pwd_context.verify(plain_password, hashed_password)
    except Exception:
        return False

def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)
