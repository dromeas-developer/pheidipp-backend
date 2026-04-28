from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text


async def check_database(session: AsyncSession) -> bool:
    try:
        result = await session.execute(text("SELECT 1"))
        return result.scalar_one() == 1
    except Exception as e:
        # Using print for visibility in container logs
        print(f"DEBUG: DB check failed with error: {type(e).__name__}: {e}")
        return False