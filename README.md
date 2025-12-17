# HTML Simulator API

An API that generates interactive educational HTML simulations using Google's Gemini AI. The API creates either 2D or 3D simulations based on educational topics and caches them locally for faster retrieval.

## Features

- 🎓 Generate educational HTML simulations using Gemini AI
- 🎨 Support for both 2D and 3D interactive simulations
- 💾 SQLite database for robust data management
- 🚀 Fast retrieval of previously generated simulations with access tracking
- 📚 Organized by topic, chapter, subject, and grade level
- 🔍 Search functionality across topics, chapters, and subjects
- 📊 Statistics and analytics on simulation usage
- 🔄 Pagination support for large datasets

## Setup

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure Environment

Create a `.env` file in the project root:

```bash
cp .env.example .env
```

Then edit `.env` and add your Gemini API key:

```
GEMINI_API_KEY=your_actual_api_key_here
```

Get your API key from: https://makersuite.google.com/app/apikey

### 3. Run the Server

```bash
python main.py
```

Or with uvicorn directly:

```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

The API will be available at `http://localhost:8000`

## API Endpoints

### Generate Simulation

**POST** `/generate`

Generates an interactive HTML simulation. Returns cached version if already exists.

**Request Body:**
```json
{
  "topic": "Photosynthesis",
  "topicID": "bio_001",
  "chapter": "Plant Biology",
  "chapterID": "ch_05",
  "subject": "Biology",
  "subjectID": "bio",
  "level": 10,
  "simulation_type": "3d"
}
```

**Response:** HTML file (ready to render in browser)

**Status Codes:**
- `200`: Cached simulation returned
- `201`: New simulation generated

### List All Simulations

**GET** `/simulations?limit=10&offset=0&subject_id=bio&level=10`

Returns a paginated list of all cached simulations with optional filtering.

**Query Parameters:**
- `limit` (optional): Number of results per page (1-100)
- `offset` (optional): Starting position for pagination
- `subject_id` (optional): Filter by subject ID
- `level` (optional): Filter by grade level

**Response:**
```json
{
  "total": 50,
  "limit": 10,
  "offset": 0,
  "count": 10,
  "simulations": [...]
}
```

### Search Simulations

**GET** `/simulations/search?q=photosynthesis&fields=topic,subject`

Search simulations by topic, chapter, or subject.

**Query Parameters:**
- `q` (required): Search query
- `fields` (optional): Comma-separated fields to search (topic,chapter,subject)

### Get Simulation Statistics

**GET** `/simulations/stats`

Returns database statistics including total simulations, unique subjects, access counts, and most accessed simulations.

**Response:**
```json
{
  "total_simulations": 50,
  "unique_subjects": 8,
  "unique_levels": 5,
  "total_accesses": 342,
  "avg_accesses_per_simulation": 6.84,
  "most_accessed": [...]
}
```

### Get Simulations by Subject and Level

**GET** `/simulations/subject/{subject_id}/level/{level}`

Get all simulations for a specific subject and level.

### Get Specific Simulation

**GET** `/simulations/{cache_key}`

Returns the HTML content of a specific simulation.

### Delete Specific Simulation

**DELETE** `/simulations/{cache_key}`

Deletes a specific cached simulation by its cache key.

### Clear All Cache

**DELETE** `/cache/clear`

Deletes all cached HTML files and database records.

## Example Usage

### Using cURL

```bash
curl -X POST http://localhost:8000/generate \
  -H "Content-Type: application/json" \
  -d '{
    "topic": "Solar System",
    "topicID": "astro_001",
    "chapter": "Astronomy Basics",
    "chapterID": "ch_01",
    "subject": "Science",
    "subjectID": "sci",
    "level": 8,
    "simulation_type": "3d"
  }' > simulation.html
```

### Using Python

```python
import requests

response = requests.post(
    "http://localhost:8000/generate",
    json={
        "topic": "Pythagorean Theorem",
        "topicID": "math_001",
        "chapter": "Geometry",
        "chapterID": "ch_03",
        "subject": "Mathematics",
        "subjectID": "math",
        "level": 9,
        "simulation_type": "2d"
    }
)

with open("simulation.html", "w") as f:
    f.write(response.text)
```

### Using JavaScript/Fetch

```javascript
fetch('http://localhost:8000/generate', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
  },
  body: JSON.stringify({
    topic: "Wave Motion",
    topicID: "phy_001",
    chapter: "Waves",
    chapterID: "ch_07",
    subject: "Physics",
    subjectID: "phy",
    level: 11,
    simulation_type: "3d"
  })
})
.then(response => response.text())
.then(html => {
  document.open();
  document.write(html);
  document.close();
});
```

## Cache System

- Simulations are cached in the `html_cache/` directory
- All metadata stored in SQLite database (`simulations.db`)
- Cache key is generated from: `topicID`, `chapterID`, `subjectID`, `level`, and `simulation_type`
- Identical requests return cached HTML instantly (no API call to Gemini)
- Automatic access tracking (timestamps and access counts)
- Database includes indexes for fast lookups by subject, level, and topic

## Simulation Types

- **3d**: Creates interactive 3D simulations using Three.js
- **2d**: Creates 2D simulations using Canvas or SVG

## Project Structure

```
html-simulator/
├── main.py              # Main FastAPI application
├── database.py          # SQLite database layer
├── requirements.txt     # Python dependencies
├── .env                 # Environment variables (create this)
├── .env.example         # Example environment file
├── simulations.db       # SQLite database (auto-created)
├── html_cache/          # Generated HTML files (auto-created)
│   └── *.html          # Cached simulation files
└── README.md           # This file
```

## Notes

- The API uses Google's Gemini 1.5 Flash model for fast generation
- Generated HTML files are self-contained with all necessary CDN links
- Simulations are designed to be educational and interactive
- Each simulation includes controls, instructions, and visual aids

## License

MIT