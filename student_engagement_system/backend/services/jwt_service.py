import os
print("JWT FILE:", __file__)

import jwt
from datetime import datetime, timedelta

SECRET_KEY = "student_engagement_secret_key"
ALGORITHM = "HS256"
TOKEN_EXPIRE_HOURS = 24


class JWTService:

    @staticmethod
    def generate_token(user_id, role):

        print("GENERATING TOKEN")
        print("SECRET:", SECRET_KEY)

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

        print("TOKEN GENERATED:", token)

        return token


    @staticmethod
    def verify_token(token):

        print("VERIFY SECRET:", SECRET_KEY)
        print("TOKEN RECEIVED:", token)

        payload = jwt.decode(
            token,
            SECRET_KEY,
            algorithms=[ALGORITHM]
        )

        return payload