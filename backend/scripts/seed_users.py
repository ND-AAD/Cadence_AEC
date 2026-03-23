"""Seed demo user accounts. Run: python -m scripts.seed_users"""

import asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

from app.core.config import settings
from app.core.auth import hash_password
from app.models.infrastructure import User

DEMO_USERS = [
    {"email": "admin@cadence-aec.io", "name": "Nick", "password": "Cad3nc3_Admin2026!"},
    # Add architect friends here before demo:
    # {"email": "friend@firm.com", "name": "Friend Name", "password": "cadence2026"},
]


async def seed_users():
    engine = create_async_engine(settings.database_url_async)
    async_session = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )

    async with async_session() as db:
        for user_data in DEMO_USERS:
            existing = await db.execute(
                select(User).where(User.email == user_data["email"])
            )
            if existing.scalar_one_or_none():
                print(f"  User {user_data['email']} already exists, skipping")
                continue

            user = User(
                email=user_data["email"],
                name=user_data["name"],
                password_hash=hash_password(user_data["password"]),
            )
            db.add(user)
            print(f"  Created user: {user_data['email']}")

        await db.commit()

    await engine.dispose()
    print("Done.")


if __name__ == "__main__":
    asyncio.run(seed_users())
