import os
import hashlib
import logging
from pathlib import Path
from typing import Optional, Union
from datetime import datetime
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, field_validator
import google.generativeai as genai
from dotenv import load_dotenv
import uvicorn

# Import database functions
from src.database import (
    get_simulation_by_cache_key,
    insert_simulation,
    get_all_simulations,
    get_simulation_count,
    delete_simulation_by_cache_key,
    delete_all_simulations,
    get_statistics,
    search_simulations,
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

load_dotenv()

# Configure Gemini API
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    logger.error("GEMINI_API_KEY environment variable is not set")
    raise ValueError("GEMINI_API_KEY environment variable is not set")

genai.configure(api_key=GEMINI_API_KEY)
MODEL_NAME = "gemini-3-pro-preview"
logger.info(f"Gemini API configured with model: {MODEL_NAME}")

# Cache directory for storing generated HTML files
CACHE_DIR = Path("html_cache")
CACHE_DIR.mkdir(exist_ok=True)
logger.info(f"Cache directory initialized at: {CACHE_DIR}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events"""
    # Startup
    logger.info("="*50)
    logger.info("HTML Simulator API Starting Up")
    logger.info(f"Version: 0.1.0")
    logger.info(f"Cache Directory: {CACHE_DIR}")
    logger.info("="*50)
    
    yield
    
    # Shutdown
    logger.info("HTML Simulator API Shutting Down")


# Initialize FastAPI app with lifespan
app = FastAPI(title="HTML Simulator API", version="0.1.0", lifespan=lifespan)


class SimulationRequest(BaseModel):
    topic: str
    topic_id: Union[int, str, None] = None
    chapter: str
    chapter_id: Union[int, str, None] = None
    subject: str
    subject_id: Union[int, str, None] = None
    level: int
    
    @field_validator('topic_id', 'chapter_id', 'subject_id', mode='before')
    @classmethod
    def convert_to_int(cls, v):
        """Convert string IDs to integers"""
        if v is None:
            return None
        if isinstance(v, int):
            return v
        if isinstance(v, str):
            try:
                return int(v)
            except ValueError:
                raise ValueError(f"ID must be a valid integer, got: {v}")
        return v

def generate_cache_key(request: SimulationRequest) -> str:
    """Generate a unique cache key based on request parameters"""
    key_string = f"{request.topic_id}_{request.chapter_id}_{request.subject_id}_{request.level}"
    cache_key = hashlib.md5(key_string.encode()).hexdigest()
    logger.debug(f"Generated cache key: {cache_key} for topic: {request.topic}")
    return cache_key


def get_cached_html(cache_key: str) -> Optional[str]:
    """Retrieve cached HTML if it exists"""
    try:
        simulation = get_simulation_by_cache_key(cache_key)
        
        if simulation:
            file_path = Path(simulation["file_path"])
            if file_path.exists():
                with open(file_path, "r", encoding="utf-8") as f:
                    content = f.read()
                logger.info(f"Retrieved cached simulation: {cache_key} (Topic: {simulation.get('topic')})")
                return content
            else:
                logger.warning(f"Database entry exists but file not found: {file_path}")
        
        return None
    except Exception as e:
        logger.error(f"Error retrieving cached HTML for key {cache_key}: {str(e)}")
        return None


def save_html_to_cache(cache_key: str, html_content: str, request: SimulationRequest):
    """Save generated HTML to cache and database"""
    try:
        file_name = f"{cache_key}.html"
        file_path = CACHE_DIR / file_name
        
        # Save HTML file
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(html_content)
        
        logger.info(f"Saved HTML file: {file_path}")
        
        # Insert into database with integer IDs
        insert_simulation(
            cache_key=cache_key,
            topic=request.topic,
            topic_id=request.topic_id,
            chapter=request.chapter,
            chapter_id=request.chapter_id,
            subject=request.subject,
            subject_id=request.subject_id,
            level=request.level,
            simulation_type="auto",
            file_path=str(file_path)
        )
        
        logger.info(f"Saved simulation to database - Topic: {request.topic}, Subject: {request.subject}, Level: {request.level}")
    except Exception as e:
        logger.error(f"Error saving simulation to cache: {str(e)}")
        raise


def generate_html_with_gemini(request: SimulationRequest) -> str:
    """Generate HTML simulation using Gemini API"""
    
    prompt = f"""
Create a complete, self-contained, interactive HTML page for an educational simulation with the following requirements:

Subject: {request.subject}
Chapter: {request.chapter}
Topic: {request.topic}
Grade/Level: {request.level}

Requirements:
1. Create a 3D interactive simulation using Three.js if required else 2D interactive simulation using Canvas or SVG
2. The simulation should be highly educational and help students understand the concept through interaction
3. Include clear instructions for the user on how to interact with the simulation
4. Add controls (sliders, buttons, inputs) to modify parameters and observe changes
5. Include educational explanations and labels
6. Make it visually appealing with good UI/UX
7. The HTML must be complete and ready to run (include all necessary CDN links)
8. Add responsive design for mobile and desktop
9. Include interactive elements that demonstrate the core concepts
10. Add reset and play/pause controls where applicable

Important:
- Use only CDN links for external libraries (Three.js for 3D, no npm packages)
- Make it production-ready and bug-free
- Focus on educational value and interactivity
- Include color-coded visual elements to aid understanding
- Add tooltips or info boxes explaining what's happening

Return ONLY the complete HTML code, nothing else. No markdown, no explanations, just the HTML.
"""
    
    try:
        logger.info(f"Generating HTML with Gemini for topic: {request.topic}")
        start_time = datetime.now()
        
        model = genai.GenerativeModel(MODEL_NAME)
        response = model.generate_content(prompt)
        
        generation_time = (datetime.now() - start_time).total_seconds()
        logger.info(f"Gemini generation completed in {generation_time:.2f} seconds")
        
        # Extract HTML from response
        html_content = response.text.strip()
        
        # Remove markdown code blocks if present
        if html_content.startswith("```html"):
            html_content = html_content[7:]
        if html_content.startswith("```"):
            html_content = html_content[3:]
        if html_content.endswith("```"):
            html_content = html_content[:-3]
        
        html_content = html_content.strip()
        
        logger.info(f"HTML content extracted, length: {len(html_content)} characters")
        
        return html_content
    
    except Exception as e:
        logger.error(f"Error generating HTML with Gemini: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error generating HTML with Gemini: {str(e)}")


@app.get("/")
def read_root():
    logger.info("Root endpoint accessed")
    return {
        "message": "HTML Simulator API",
        "version": "0.1.0",
        "endpoints": {
            "/generate": "POST - Generate HTML simulation",
            "/simulations": "GET - List all cached simulations (with pagination)",
            "/simulations/search": "GET - Search simulations",
            "/simulations/stats": "GET - Get database statistics",
            "/simulations/{cache_key}": "GET - Get specific simulation",
            "/simulations/{cache_key}": "DELETE - Delete specific simulation",
            "/cache/clear": "DELETE - Clear all cache"
        }
    }


@app.post("/generate", response_class=HTMLResponse)
async def generate_simulation(request: SimulationRequest):
    """
    Generate an interactive HTML simulation for educational purposes.
    Returns cached version if already generated, otherwise creates new one using Gemini.
    """
    
    logger.info(f"Generation request received - Topic: {request.topic}, Subject: {request.subject}, Level: {request.level}")
    
    try:
        # Generate cache key
        cache_key = generate_cache_key(request)
        
        # Check if cached version exists
        cached_html = get_cached_html(cache_key)
        if cached_html:
            logger.info(f"Returning cached simulation for key: {cache_key}")
            return HTMLResponse(content=cached_html, status_code=200)
        
        logger.info(f"No cache found, generating new simulation for key: {cache_key}")
        
        # Generate new HTML using Gemini
        html_content = generate_html_with_gemini(request)
        
        # Save to cache
        save_html_to_cache(cache_key, html_content, request)
        
        logger.info(f"Successfully generated and cached new simulation for key: {cache_key}")
        return HTMLResponse(content=html_content, status_code=201)
    
    except Exception as e:
        logger.error(f"Error in generate_simulation endpoint: {str(e)}", exc_info=True)
        raise


@app.get("/simulations")
def list_simulations(
    limit: Optional[int] = Query(None, ge=1, le=100),
    offset: int = Query(0, ge=0),
    level: Optional[int] = None
):
    """List all cached simulations with optional filtering and pagination"""
    logger.info(f"Listing simulations - limit: {limit}, offset: {offset}, level: {level}")
    
    try:
        simulations = get_all_simulations(
            limit=limit,
            offset=offset,
            level=level
        )
        
        total = get_simulation_count(level=level)
        
        logger.info(f"Retrieved {len(simulations)} simulations (total: {total})")
        
        return {
            "total": total,
            "limit": limit,
            "offset": offset,
            "count": len(simulations),
            "simulations": simulations
        }
    except Exception as e:
        logger.error(f"Error listing simulations: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error retrieving simulations: {str(e)}")


@app.get("/simulations/search")
def search_simulations_endpoint(
    q: str = Query(..., min_length=1, description="Search query"),
    fields: Optional[str] = Query(None, description="Comma-separated fields to search (topic,chapter,subject)")
):
    """Search simulations by topic, chapter, or subject"""
    logger.info(f"Search request - query: '{q}', fields: {fields}")
    
    try:
        search_fields = None
        if fields:
            search_fields = [f.strip() for f in fields.split(",")]
        
        results = search_simulations(q, search_fields)
        
        logger.info(f"Search returned {len(results)} results for query: '{q}'")
        
        return {
            "query": q,
            "count": len(results),
            "results": results
        }
    except Exception as e:
        logger.error(f"Error searching simulations: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error searching simulations: {str(e)}")


@app.get("/simulations/stats")
def get_simulation_statistics():
    """Get database statistics including total simulations, subjects, and most accessed"""
    logger.info("Statistics request received")
    
    try:
        stats = get_statistics()
        logger.info(f"Statistics retrieved - Total simulations: {stats.get('total_simulations', 0)}")
        return stats
    except Exception as e:
        logger.error(f"Error retrieving statistics: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error retrieving statistics: {str(e)}")


@app.get("/simulations/{cache_key}", response_class=HTMLResponse)
def get_simulation(cache_key: str):
    """Get a specific simulation HTML by cache key"""
    logger.info(f"Fetching simulation with cache_key: {cache_key}")
    
    try:
        html_content = get_cached_html(cache_key)
        
        if not html_content:
            logger.warning(f"Simulation not found for cache_key: {cache_key}")
            raise HTTPException(status_code=404, detail="Simulation not found")
        
        return HTMLResponse(content=html_content, status_code=200)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving simulation: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error retrieving simulation: {str(e)}")


@app.delete("/simulations/{cache_key}")
def delete_simulation(cache_key: str):
    """Delete a specific cached simulation"""
    logger.info(f"Delete request for simulation: {cache_key}")
    
    try:
        simulation = get_simulation_by_cache_key(cache_key)
        
        if not simulation:
            logger.warning(f"Simulation not found for deletion: {cache_key}")
            raise HTTPException(status_code=404, detail="Simulation not found")
        
        # Delete file
        file_path = Path(simulation["file_path"])
        if file_path.exists():
            file_path.unlink()
            logger.info(f"Deleted file: {file_path}")
        else:
            logger.warning(f"File not found for deletion: {file_path}")
        
        # Delete from database
        deleted = delete_simulation_by_cache_key(cache_key)
        
        if not deleted:
            logger.error(f"Failed to delete simulation from database: {cache_key}")
            raise HTTPException(status_code=500, detail="Failed to delete simulation from database")
        
        logger.info(f"Successfully deleted simulation: {cache_key}")
        return {"message": f"Simulation {cache_key} deleted successfully"}
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting simulation: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error deleting simulation: {str(e)}")


@app.delete("/cache/clear")
def clear_cache():
    """Clear all cached simulations"""
    logger.warning("Cache clear request received - deleting all simulations")
    
    try:
        # Get all simulations
        simulations = get_all_simulations()
        
        # Delete all HTML files
        deleted_files = 0
        for simulation in simulations:
            file_path = Path(simulation["file_path"])
            if file_path.exists():
                file_path.unlink()
                deleted_files += 1
        
        logger.info(f"Deleted {deleted_files} HTML files")
        
        # Delete all database records
        count = delete_all_simulations()
        
        logger.info(f"Cleared {count} database records")
        
        return {
            "message": "Cache cleared successfully",
            "deleted_count": count,
            "deleted_files": deleted_files
        }
    except Exception as e:
        logger.error(f"Error clearing cache: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error clearing cache: {str(e)}")

