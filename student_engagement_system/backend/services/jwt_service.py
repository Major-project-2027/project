import os
print("JWT FILE:", __file__)

import jwt
from datetime import datetime, timedelta

from config import SECRET_KEY

# No fallback on purpose: SECRET_KEY signs and verifies every login token,
# so a default would let anyone who knows it forge tokens. Fail at import
# (i.e. the Flask service refuses to start) instead of running with a
# guessable key.
if not (SECRET_KEY or "").strip():
    raise RuntimeError(
        "SECRET_KEY is not set. It is required to sign and verify login "
        "tokens -- set it in backend/.env for local development, or in the "
        "service's environment variables on Render."
    )

ALGORITHM = "HS256"
TOKEN_EXPIRE_HOURS = 24


class JWTService:

    @staticmethod
    def generate_token(user_id, role):

        print("GENERATING TOKEN")

        payload = {
            "user_id": user_id,
            "role": role,
            "exp": datetime.utcnow() + timedelta(hours=TOKEN_EXPIRE_HOURS)
        }

        token = jwt.encode(
            payload,
            SECRET_KEY,
            algorithm=ALGORITHM
        )

        print("TOKEN GENERATED")

        return token


    @staticmethod
    def verify_token(token):

        print("TOKEN RECEIVED")

        payload = jwt.decode(
            token,
            SECRET_KEY,
            algorithms=[ALGORITHM]
        )

        return payload