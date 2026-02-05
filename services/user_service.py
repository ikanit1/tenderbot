# services/user_service.py — бизнес-логика работы с пользователями
import logging
from typing import Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import User, UserStatus, UserRole
from config import settings
from utils.cache import cached, get_cache

logger = logging.getLogger(__name__)


class UserService:
    """Сервис для работы с пользователями."""
    
    @staticmethod
    async def get_user_by_tg_id(
        session: AsyncSession,
        tg_id: int,
        use_cache: bool = True,
    ) -> Optional[User]:
        """
        Получить пользователя по Telegram ID.
        
        Args:
            session: Сессия БД
            tg_id: Telegram ID пользователя
            use_cache: Использовать ли кэш
        
        Returns:
            User или None
        """
        if use_cache:
            cache = get_cache()
            cache_key = f"user:tg_id:{tg_id}"
            cached_user = cache.get(cache_key)
            if cached_user is not None:
                return cached_user
        
        result = await session.execute(select(User).where(User.tg_id == tg_id))
        user = result.scalar_one_or_none()
        
        if user and use_cache:
            cache.set(cache_key, user, ttl=settings.CACHE_TTL_USER_PROFILE)
        
        return user
    
    @staticmethod
    async def get_user_by_id(
        session: AsyncSession,
        user_id: int,
    ) -> Optional[User]:
        """Получить пользователя по ID."""
        result = await session.execute(select(User).where(User.id == user_id))
        return result.scalar_one_or_none()
    
    @staticmethod
    async def update_user_status(
        session: AsyncSession,
        user_id: int,
        new_status: str,
    ) -> Optional[User]:
        """
        Обновить статус пользователя.
        
        Args:
            session: Сессия БД
            user_id: ID пользователя
            new_status: Новый статус
        
        Returns:
            Обновленный User или None
        """
        user = await UserService.get_user_by_id(session, user_id)
        if not user:
            return None
        
        old_status = user.status
        user.status = new_status
        await session.flush()
        
        # Инвалидируем кэш
        cache = get_cache()
        cache.delete(f"user:tg_id:{user.tg_id}")
        
        logger.info(f"User {user_id} status changed: {old_status} -> {new_status}")
        return user
    
    @staticmethod
    async def is_user_active(
        session: AsyncSession,
        tg_id: int,
    ) -> bool:
        """Проверить, активен ли пользователь."""
        user = await UserService.get_user_by_tg_id(session, tg_id)
        return user is not None and user.status == UserStatus.ACTIVE.value
    
    @staticmethod
    async def can_user_apply_to_tenders(
        session: AsyncSession,
        tg_id: int,
    ) -> bool:
        """Проверить, может ли пользователь откликаться на тендеры."""
        user = await UserService.get_user_by_tg_id(session, tg_id)
        if not user:
            return False
        
        return (
            user.status == UserStatus.ACTIVE.value
            and user.role in (UserRole.EXECUTOR.value, UserRole.BOTH.value)
        )
