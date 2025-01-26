# api/main.py

import os
from dotenv import load_dotenv
from fastapi import FastAPI
from logging import getLogger
from contextlib import asynccontextmanager
from supabase import create_client, Client

from api.journal.journal_recording import JournalRecordingHandler
from api.utils.logger import setup_logger
from api.utils.constants import SHARED
from api.find.search_agent import SearchAgent
from api.integration.extraction_agent import ExtractionAgent
from api.email.email_extraction_agent import EmailExtractionAgent

# Routers
from api.core.main_router import router as main_router
from api.find.router import router as find_router
from api.integration.router import router as integration_router
from api.email.router import router as email_router
from api.journal.router import router as journal_router
from api.whatsapp.router import router as whatsapp_router
from api.whatsapp.webhook_router import webhook_router
from api.journal.journal_handler import JournalHandler

load_dotenv()
setup_logger()

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger = getLogger("API")
    # Initialize resources during startup
    try:
        SHARED["search_companies"] = SearchAgent("companies")
    except Exception as e:
        logger.error(f"Failed to initialize search_companies: {e}")

    try:
        SHARED["extraction_agent"] = ExtractionAgent()
    except Exception as e:
        logger.error(f"Failed to initialize extraction_agent: {e}")

    try:
        SUPABASE_URL = os.getenv("SUPABASE_URL")
        SUPABASE_KEY = os.getenv("SUPABASE_KEY")
        supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
        SHARED["supabase_client"] = supabase

        try:
            SHARED["journal_handler"] = JournalHandler(supabase=supabase)
        except Exception as e:
            logger.error(f"Failed to initialize journal_handler: {e}")

        try:
            SHARED["journal_recording_handler"] = JournalRecordingHandler(supabase=supabase)
        except Exception as e:
            logger.error(f"Failed to initialize journal_recording_handler: {e}")

    except Exception as e:
        logger.error(f"Failed to initialize Supabase client: {e}")


    try:
        SHARED["email_agent"] = EmailExtractionAgent()
    except Exception as e:
        logger.error(f"Failed to initialize email_agent: {e}")

    logger.info("Startup completed. Resources initialized.")

    yield  # Application is running

    # Clean up resources during shutdown
    SHARED.clear()
    logger.info("Shutdown completed. Resources cleaned up.")

app = FastAPI(
    lifespan=lifespan,
    description="Sammy API",
    title="Sammy API",
    version="0.1.0",
    contact={
        "name": "Sammy API",
        "url": "https://sammy.club",
    },
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
app.include_router(main_router)
app.include_router(find_router)
app.include_router(integration_router)
app.include_router(journal_router)
app.include_router(email_router)
app.include_router(whatsapp_router)
app.include_router(webhook_router)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001, log_level="debug")
