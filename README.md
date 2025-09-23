<div align="center">
<img width="1200" height="475" alt="GHBanner" src="https://github.com/user-attachments/assets/0aa67016-6eaf-458a-adb2-6e31a0763ed6" />
</div>

# HR Resume Ranker

An AI-powered resume ranking system that helps HR professionals evaluate and rank candidates based on job descriptions. The application is now split into a FastAPI backend and React frontend for better scalability and maintainability.

## Architecture

- **Backend**: FastAPI with Python for AI processing and API endpoints
- **Frontend**: React with TypeScript and Tailwind CSS for the user interface
- **AI Engine**: OpenAI ChatGPT API for resume analysis and ranking

## Features

- Upload multiple resumes in ZIP format
- AI-powered candidate evaluation using ChatGPT
- Automatic GitHub profile detection and validation
- Skill-based ranking and categorization (Python, AI libraries, ML exposure, AI projects)
- Modern, responsive web interface
- Real-time progress tracking
- RESTful API architecture

## Project Structure

```
HR-Resume-Ranker/
├── backend/                 # FastAPI backend
│   ├── main.py             # Main FastAPI application
│   ├── requirements.txt    # Python dependencies
│   ├── models/
│   │   └── schemas.py      # Pydantic models
│   ├── services/
│   │   └── openai_service.py # AI processing service
│   └── .env.example        # Environment variables template
├── frontend/               # React frontend
│   ├── src/
│   │   ├── components/     # React components
│   │   ├── services/       # API service layer
│   │   ├── types/          # TypeScript type definitions
│   │   └── App.tsx         # Main React application
│   ├── package.json        # Node.js dependencies
│   └── vite.config.ts      # Vite configuration
└── README.md               # This file
```

## Setup Instructions

### Backend Setup

1. Navigate to the backend directory:
   ```bash
   cd backend
   ```

2. Create a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. Install Python dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Set up environment variables:
   ```bash
   cp .env.example .env
   # Edit .env and add your OpenAI API key
   ```

5. Start the FastAPI server:
   ```bash
   python main.py
   ```
   
   The backend will be available at `http://localhost:8000`

### Frontend Setup

1. Navigate to the frontend directory:
   ```bash
   cd frontend
   ```

2. Install Node.js dependencies:
   ```bash
   npm install
   ```

3. Start the development server:
   ```bash
   npm run dev
   ```
   
   The frontend will be available at `http://localhost:3000`

## Environment Variables

Create a `.env` file in the backend directory with the following:

```
OPENAI_API_KEY=your_openai_api_key_here
OPENAI_MODEL=gpt-4o-mini
```

To get an OpenAI API key:
1. Visit [platform.openai.com](https://platform.openai.com/)
2. Create a new API key with access to the Chat Completions API
3. Copy the key to your `.env` file

### Frontend Environment Variables

For the standalone React client in the project root, create a `.env` file alongside `package.json` with:

```
VITE_OPENAI_API_KEY=your_openai_api_key_here
VITE_OPENAI_MODEL=gpt-4o-mini
```

Restart the Vite development server after updating these values.

## Usage

1. Start both the backend and frontend servers
2. Open your browser to `http://localhost:3000`
3. Provide a detailed job description
4. Upload a ZIP file containing candidate resumes (PDF format)
5. Click "Rank Candidates" to start the AI analysis
6. Review the ranked results and candidate insights

## API Endpoints

- `GET /` - Root endpoint
- `GET /health` - Health check
- `POST /api/rank-resumes` - Main resume ranking endpoint

## Development

### Backend Development
- The backend uses FastAPI with automatic API documentation at `http://localhost:8000/docs`
- Rate limiting is implemented for the ChatGPT API
- PDF processing is handled server-side

### Frontend Development
- Built with React 18 and TypeScript
- Styled with Tailwind CSS
- Uses Axios for API communication
- Vite for fast development and building

## Production Deployment

### Backend
```bash
cd backend
pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 8000
```

### Frontend
```bash
cd frontend
npm run build
# Serve the dist/ directory with your preferred web server
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test both backend and frontend
5. Submit a pull request
