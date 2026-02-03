# run.py — единый запуск бота и веб-интерфейса
import asyncio
import logging
import multiprocessing
import sys
from pathlib import Path

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def run_bot():
    """Запуск Telegram бота."""
    try:
        # Импортируем main, который уже выполнит миграции
        from main import main as bot_main
        import asyncio
        asyncio.run(bot_main())
    except KeyboardInterrupt:
        logger.info("Бот остановлен")
    except Exception as e:
        logger.error(f"Ошибка в боте: {e}", exc_info=True)
        sys.exit(1)


def run_web():
    """Запуск веб-интерфейса."""
    try:
        import uvicorn
        from config import settings
        
        logger.info(f"Запуск веб-интерфейса на http://{settings.WEB_HOST}:{settings.WEB_PORT}")
        uvicorn.run(
            "web.main:app",
            host=settings.WEB_HOST,
            port=settings.WEB_PORT,
            reload=False,
            log_level="info",
        )
    except KeyboardInterrupt:
        logger.info("Веб-интерфейс остановлен")
    except Exception as e:
        logger.error(f"Ошибка в веб-интерфейсе: {e}", exc_info=True)
        sys.exit(1)


def main():
    """Запуск бота и веб-интерфейса в отдельных процессах."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Запуск TenderBot (бот + веб-интерфейс)")
    parser.add_argument(
        "--bot-only",
        action="store_true",
        help="Запустить только бота",
    )
    parser.add_argument(
        "--web-only",
        action="store_true",
        help="Запустить только веб-интерфейс",
    )
    args = parser.parse_args()
    
    if args.bot_only:
        logger.info("Запуск только бота...")
        run_bot()
    elif args.web_only:
        logger.info("Запуск только веб-интерфейса...")
        run_web()
    else:
        logger.info("Запуск бота и веб-интерфейса...")
        
        # Создаём процессы
        bot_process = multiprocessing.Process(target=run_bot, name="BotProcess")
        web_process = multiprocessing.Process(target=run_web, name="WebProcess")
        
        try:
            # Запускаем оба процесса
            bot_process.start()
            web_process.start()
            
            # Импортируем settings для получения порта
            from config import settings
            
            logger.info("✅ Бот и веб-интерфейс запущены")
            logger.info("   Бот: работает в фоне")
            logger.info(f"   Веб: http://{settings.WEB_HOST}:{settings.WEB_PORT}")
            
            # Ждём завершения процессов
            bot_process.join()
            web_process.join()
            
        except KeyboardInterrupt:
            logger.info("\n🛑 Остановка сервисов...")
            bot_process.terminate()
            web_process.terminate()
            bot_process.join(timeout=5)
            web_process.join(timeout=5)
            logger.info("✅ Сервисы остановлены")
        except Exception as e:
            logger.error(f"Ошибка при запуске: {e}", exc_info=True)
            bot_process.terminate()
            web_process.terminate()
            sys.exit(1)


if __name__ == "__main__":
    # Для Windows нужно использовать spawn вместо fork
    if sys.platform == "win32":
        multiprocessing.set_start_method("spawn", force=True)
    
    main()

