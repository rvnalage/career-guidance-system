# Career Guidance System - Complete Project Setup Script
# Run: .\setup-project.ps1

Write-Host ""
Write-Host "================================================" -ForegroundColor Cyan
Write-Host "   Career Guidance System - Project Setup" -ForegroundColor Cyan
Write-Host "================================================" -ForegroundColor Cyan
Write-Host ""

# Configuration
$ProjectName = "career-guidance-system"
$CurrentPath = Get-Location
$ProjectPath = Join-Path $CurrentPath $ProjectName

# Create main project directory
Write-Host "[*] Creating main project directory..." -ForegroundColor Yellow
New-Item -ItemType Directory -Path $ProjectPath -Force | Out-Null
Set-Location $ProjectPath
Write-Host "[OK] Project directory created at: $ProjectPath" -ForegroundColor Green
Write-Host ""

# ===== BACKEND STRUCTURE =====
Write-Host "================================================" -ForegroundColor Cyan
Write-Host "   Creating Backend Structure" -ForegroundColor Cyan
Write-Host "================================================" -ForegroundColor Cyan

$BackendDirs = @(
  "backend\app\api\routes",
  "backend\app\api\middleware",
  "backend\app\services",
  "backend\app\nlp",
  "backend\app\agents",
  "backend\app\ml",
  "backend\app\xai",
  "backend\app\rag",
  "backend\app\database",
  "backend\app\utils",
  "backend\app\schemas",
  "backend\tests",
  "backend\scripts"
)

Write-Host "[*] Creating backend directories..." -ForegroundColor Yellow
foreach ($dir in $BackendDirs) {
  New-Item -ItemType Directory -Path $dir -Force | Out-Null
}
Write-Host "[OK] Backend directories created" -ForegroundColor Green

# Create backend Python files
Write-Host "[*] Creating backend Python files..." -ForegroundColor Yellow
$BackendPyFiles = @(
  "backend\app\__init__.py",
  "backend\app\main.py",
  "backend\app\config.py",
  "backend\app\dependencies.py",
  "backend\app\api\__init__.py",
  "backend\app\api\routes\__init__.py",
  "backend\app\api\routes\auth.py",
  "backend\app\api\routes\chat.py",
  "backend\app\api\routes\users.py",
  "backend\app\api\routes\recommendations.py",
  "backend\app\api\routes\history.py",
  "backend\app\api\routes\dashboard.py",
  "backend\app\api\middleware\__init__.py",
  "backend\app\api\middleware\auth_middleware.py",
  "backend\app\api\middleware\error_handler.py",
  "backend\app\services\__init__.py",
  "backend\app\services\user_service.py",
  "backend\app\services\chat_service.py",
  "backend\app\services\history_service.py",
  "backend\app\services\recommendation_service.py",
  "backend\app\services\agent_service.py",
  "backend\app\nlp\__init__.py",
  "backend\app\nlp\text_processor.py",
  "backend\app\nlp\embeddings.py",
  "backend\app\nlp\intent_recognizer.py",
  "backend\app\nlp\summarizer.py",
  "backend\app\agents\__init__.py",
  "backend\app\agents\base_agent.py",
  "backend\app\agents\career_assessment_agent.py",
  "backend\app\agents\job_matching_agent.py",
  "backend\app\agents\learning_path_agent.py",
  "backend\app\agents\interview_prep_agent.py",
  "backend\app\agents\networking_agent.py",
  "backend\app\ml\__init__.py",
  "backend\app\ml\models.py",
  "backend\app\ml\feature_engineering.py",
  "backend\app\ml\training.py",
  "backend\app\ml\inference.py",
  "backend\app\xai\__init__.py",
  "backend\app\xai\explainer.py",
  "backend\app\xai\interpretability.py",
  "backend\app\rag\__init__.py",
  "backend\app\rag\vector_store.py",
  "backend\app\rag\retriever.py",
  "backend\app\rag\web_scraper.py",
  "backend\app\rag\knowledge_base.py",
  "backend\app\database\__init__.py",
  "backend\app\database\postgres_db.py",
  "backend\app\database\mongo_db.py",
  "backend\app\database\models.py",
  "backend\app\utils\__init__.py",
  "backend\app\utils\logger.py",
  "backend\app\utils\validators.py",
  "backend\app\utils\constants.py",
  "backend\app\utils\helpers.py",
  "backend\app\schemas\__init__.py",
  "backend\app\schemas\user.py",
  "backend\app\schemas\chat.py",
  "backend\app\schemas\recommendation.py",
  "backend\app\schemas\common.py",
  "backend\tests\__init__.py",
  "backend\tests\conftest.py",
  "backend\tests\test_auth.py",
  "backend\tests\test_chat.py",
  "backend\tests\test_nlp.py",
  "backend\tests\test_agents.py",
  "backend\tests\test_ml.py",
  "backend\tests\test_integration.py",
  "backend\scripts\__init__.py",
  "backend\scripts\setup_db.py",
  "backend\scripts\seed_data.py",
  "backend\scripts\setup_vector_db.py",
  "backend\scripts\train_models.py",
  "backend\scripts\migrate.py"
)

foreach ($file in $BackendPyFiles) {
  New-Item -ItemType File -Path $file -Force | Out-Null
}

$BackendPyFileCount = ($BackendPyFiles | Measure-Object).Count
Write-Host "[OK] Backend Python files created - $BackendPyFileCount total" -ForegroundColor Green
Write-Host ""

# ===== FRONTEND STRUCTURE =====
Write-Host "================================================" -ForegroundColor Cyan
Write-Host "   Creating Frontend Structure" -ForegroundColor Cyan
Write-Host "================================================" -ForegroundColor Cyan

$FrontendDirs = @(
  "frontend\public",
  "frontend\src\components\Chat",
  "frontend\src\components\Dashboard",
  "frontend\src\components\Profile",
  "frontend\src\components\Auth",
  "frontend\src\components\Common",
  "frontend\src\components\Visualizations",
  "frontend\src\pages",
  "frontend\src\services",
  "frontend\src\hooks",
  "frontend\src\context",
  "frontend\src\styles",
  "frontend\src\utils"
)

Write-Host "[*] Creating frontend directories..." -ForegroundColor Yellow
foreach ($dir in $FrontendDirs) {
  New-Item -ItemType Directory -Path $dir -Force | Out-Null
}
Write-Host "[OK] Frontend directories created" -ForegroundColor Green

# Create frontend files
Write-Host "[*] Creating frontend files..." -ForegroundColor Yellow
$FrontendFiles = @(
  "frontend\src\App.jsx",
  "frontend\src\main.jsx",
  "frontend\src\components\Chat\ChatInterface.jsx",
  "frontend\src\components\Chat\MessageList.jsx",
  "frontend\src\components\Chat\InputBox.jsx",
  "frontend\src\components\Dashboard\Dashboard.jsx",
  "frontend\src\components\Dashboard\CareerOptions.jsx",
  "frontend\src\components\Dashboard\SkillsGapAnalysis.jsx",
  "frontend\src\components\Dashboard\Recommendations.jsx",
  "frontend\src\components\Profile\UserProfile.jsx",
  "frontend\src\components\Profile\SkillsProfile.jsx",
  "frontend\src\components\Auth\Login.jsx",
  "frontend\src\components\Auth\Register.jsx",
  "frontend\src\components\Common\Header.jsx",
  "frontend\src\components\Common\Sidebar.jsx",
  "frontend\src\components\Common\Footer.jsx",
  "frontend\src\components\Visualizations\CareerPathChart.jsx",
  "frontend\src\components\Visualizations\SkillsRadar.jsx",
  "frontend\src\components\Visualizations\JobMarketTrends.jsx",
  "frontend\src\pages\Home.jsx",
  "frontend\src\pages\Chat.jsx",
  "frontend\src\pages\Dashboard.jsx",
  "frontend\src\pages\Profile.jsx",
  "frontend\src\pages\Settings.jsx",
  "frontend\src\services\api.js",
  "frontend\src\services\auth.js",
  "frontend\src\services\socket.js",
  "frontend\src\hooks\useAuth.js",
  "frontend\src\hooks\useChat.js",
  "frontend\src\hooks\useDashboard.js",
  "frontend\src\context\AuthContext.jsx",
  "frontend\src\context\ChatContext.jsx",
  "frontend\src\context\AppContext.jsx",
  "frontend\src\styles\globals.css",
  "frontend\src\styles\tailwind.config.js",
  "frontend\src\utils\formatters.js",
  "frontend\src\utils\validators.js",
  "frontend\public\index.html",
  "frontend\public\favicon.ico"
)

foreach ($file in $FrontendFiles) {
  New-Item -ItemType File -Path $file -Force | Out-Null
}

$FrontendFileCount = ($FrontendFiles | Measure-Object).Count
Write-Host "[OK] Frontend files created - $FrontendFileCount total" -ForegroundColor Green
Write-Host ""

# ===== ML MODELS STRUCTURE =====
Write-Host "================================================" -ForegroundColor Cyan
Write-Host "   Creating ML Models Structure" -ForegroundColor Cyan
Write-Host "================================================" -ForegroundColor Cyan

$MLDirs = @(
  "ml-models\training",
  "ml-models\pretrained",
  "ml-models\datasets",
  "ml-models\evaluation"
)

Write-Host "[*] Creating ML directories..." -ForegroundColor Yellow
foreach ($dir in $MLDirs) {
  New-Item -ItemType Directory -Path $dir -Force | Out-Null
}
Write-Host "[OK] ML directories created" -ForegroundColor Green

Write-Host "[*] Creating ML files..." -ForegroundColor Yellow
$MLFiles = @(
  "ml-models\training\__init__.py",
  "ml-models\training\train_xgboost.py",
  "ml-models\training\train_catboost.py",
  "ml-models\training\train_embeddings.py",
  "ml-models\training\train_rlhf.py",
  "ml-models\evaluation\__init__.py",
  "ml-models\evaluation\metrics.py",
  "ml-models\pretrained\.gitkeep",
  "ml-models\datasets\.gitkeep"
)

foreach ($file in $MLFiles) {
  New-Item -ItemType File -Path $file -Force | Out-Null
}

$MLFileCount = ($MLFiles | Measure-Object).Count
Write-Host "[OK] ML files created - $MLFileCount total" -ForegroundColor Green
Write-Host ""

# ===== CONFIG & KUBERNETES STRUCTURE =====
Write-Host "================================================" -ForegroundColor Cyan
Write-Host "   Creating Config & Kubernetes Structure" -ForegroundColor Cyan
Write-Host "================================================" -ForegroundColor Cyan

$ConfigDirs = @(
  "config",
  "kubernetes",
  ".github\workflows",
  "scripts"
)

Write-Host "[*] Creating config directories..." -ForegroundColor Yellow
foreach ($dir in $ConfigDirs) {
  New-Item -ItemType Directory -Path $dir -Force | Out-Null
}
Write-Host "[OK] Config directories created" -ForegroundColor Green

Write-Host "[*] Creating config files..." -ForegroundColor Yellow
$ConfigFiles = @(
  "config\development.yaml",
  "config\production.yaml",
  "config\testing.yaml",
  "config\logging.yaml",
  "kubernetes\backend-deployment.yaml",
  "kubernetes\frontend-deployment.yaml",
  "kubernetes\postgres-deployment.yaml",
  "kubernetes\mongodb-deployment.yaml",
  "kubernetes\service.yaml",
  "kubernetes\ingress.yaml",
  "kubernetes\configmap.yaml",
  ".github\workflows\ci-cd.yml",
  ".github\workflows\deploy.yml",
  "scripts\setup_db.py",
  "scripts\seed_data.py"
)

foreach ($file in $ConfigFiles) {
  New-Item -ItemType File -Path $file -Force | Out-Null
}

$ConfigFileCount = ($ConfigFiles | Measure-Object).Count
Write-Host "[OK] Config files created - $ConfigFileCount total" -ForegroundColor Green
Write-Host ""

# ===== CREATE CONTENT FILES =====
Write-Host "================================================" -ForegroundColor Cyan
Write-Host "   Creating Content Files" -ForegroundColor Cyan
Write-Host "================================================" -ForegroundColor Cyan

# requirements.txt
Write-Host "[*] Creating requirements.txt..." -ForegroundColor Yellow
$RequirementsContent = @"
# Core Framework
fastapi==0.104.1
uvicorn[standard]==0.24.0
python-multipart==0.0.6

# Database
sqlalchemy==2.0.23
psycopg2-binary==2.9.9
pymongo==4.6.0
motor==3.3.2

# Authentication & Security
python-jose[cryptography]==3.3.0
passlib[bcrypt]==1.7.4
pydantic==2.5.0
pydantic-settings==2.1.0

# NLP & Embeddings
transformers==4.35.2
torch==2.1.1
sentence-transformers==2.2.2
spacy==3.7.2
nltk==3.8.1

# Agentic AI
langchain==0.1.0
langchain-openai==0.0.5
llama-index==0.9.31
openai==1.3.6

# ML & Recommendation
xgboost==2.0.3
catboost==1.2.2
lightgbm==4.0.0
scikit-learn==1.3.2
numpy==1.26.2
pandas==2.1.3

# Explainability (XAI)
shap==0.43.0
captum==0.7.0
lime==0.2.0

# Vector Databases
pinecone-client==3.0.0
weaviate-client==4.1.1
faiss-cpu==1.7.4

# Utilities
requests==2.31.0
aiohttp==3.9.1
python-dotenv==1.0.0
pydantic-extra-types==2.1.0

# Logging & Monitoring
python-json-logger==2.0.7
prometheus-client==0.19.0

# Testing
pytest==7.4.3
pytest-asyncio==0.21.1
pytest-cov==4.1.0
httpx==0.25.2

# Development
black==23.12.0
flake8==6.1.0
mypy==1.7.1
isort==5.13.2
"@

Set-Content -Path "backend\requirements.txt" -Value $RequirementsContent -Encoding ASCII
Write-Host "[OK] requirements.txt created" -ForegroundColor Green

# requirements-dev.txt
Write-Host "[*] Creating requirements-dev.txt..." -ForegroundColor Yellow
$RequirementsDevContent = @"
-r requirements.txt

# Development Tools
jupyter==1.0.0
notebook==7.0.6
ipython==8.18.1

# Code Quality
pylint==3.0.3
bandit==1.7.5
pre-commit==3.5.0

# API Documentation
mkdocs==1.5.3
mkdocs-material==9.4.14

# Debugging
ipdb==0.13.13
"@

Set-Content -Path "backend\requirements-dev.txt" -Value $RequirementsDevContent -Encoding ASCII
Write-Host "[OK] requirements-dev.txt created" -ForegroundColor Green

# package.json
Write-Host "[*] Creating package.json..." -ForegroundColor Yellow
$PackageJsonContent = '{
  "name": "career-guidance-frontend",
  "version": "1.0.0",
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "vite build",
    "preview": "vite preview",
    "lint": "eslint src --ext .js,.jsx",
    "format": "prettier --write src/**/*"
  },
  "dependencies": {
    "react": "^18.2.0",
    "react-dom": "^18.2.0",
    "react-router-dom": "^6.20.1",
    "axios": "^1.6.2",
    "zustand": "^4.4.7",
    "react-query": "^3.39.3",
    "socket.io-client": "^4.7.2",
    "recharts": "^2.10.4",
    "react-markdown": "^9.0.1",
    "tailwindcss": "^3.3.6",
    "headlessui": "^1.7.17",
    "@heroicons/react": "^2.0.18",
    "date-fns": "^2.30.0",
    "clsx": "^2.0.0"
  },
  "devDependencies": {
    "@vitejs/plugin-react": "^4.2.1",
    "vite": "^5.0.8",
    "eslint": "^8.55.0",
    "eslint-plugin-react": "^7.33.2",
    "prettier": "^3.1.1",
    "tailwindcss": "^3.3.6",
    "postcss": "^8.4.32",
    "autoprefixer": "^10.4.16"
  }
}'

Set-Content -Path "frontend\package.json" -Value $PackageJsonContent -Encoding ASCII
Write-Host "[OK] package.json created" -ForegroundColor Green

# Backend .env.example
Write-Host "[*] Creating backend .env.example..." -ForegroundColor Yellow
$BackendEnvContent = @"
ENV=development
DEBUG=True
APP_NAME=Career Guidance System
APP_VERSION=1.0.0
SECRET_KEY=your-secret-key-here-change-in-production
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
POSTGRES_URL=postgresql://postgres:rahulpg@localhost:5432/postgres
POSTGRES_USER=postgres
POSTGRES_PASSWORD=rahulpg
POSTGRES_DB=postgres
MONGODB_URL=mongodb://localhost:27017
MONGODB_DB=career_chat_history
PINECONE_API_KEY=your-pinecone-api-key
PINECONE_ENVIRONMENT=us-east1-aws
PINECONE_INDEX=career-knowledge
WEAVIATE_URL=http://localhost:8080
WEAVIATE_APIKEY=your-weaviate-key
OPENAI_API_KEY=your-openai-api-key
OPENAI_MODEL=gpt-4-turbo-preview
EMBEDDING_MODEL=text-embedding-3-large
LANGCHAIN_API_KEY=your-langchain-api-key
LANGCHAIN_TRACING_V2=true
REDIS_URL=redis://localhost:6379/0
AWS_ACCESS_KEY_ID=your-aws-key
AWS_SECRET_ACCESS_KEY=your-aws-secret
AWS_REGION=us-east-1
AWS_S3_BUCKET=career-guidance-bucket
LOG_LEVEL=INFO
LOG_FILE=logs/app.log
ALLOWED_ORIGINS=["http://localhost:3000","http://localhost:5173"]
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
SMTP_EMAIL=your-email@gmail.com
SMTP_PASSWORD=your-app-password
"@

Set-Content -Path "backend\.env.example" -Value $BackendEnvContent -Encoding ASCII
Write-Host "[OK] backend .env.example created" -ForegroundColor Green

# Frontend .env.example
Write-Host "[*] Creating frontend .env.example..." -ForegroundColor Yellow
$FrontendEnvContent = @"
VITE_API_URL=http://localhost:8000/api/v1
VITE_WS_URL=ws://localhost:8000/ws
VITE_APP_NAME=Career Guidance System
VITE_LOG_LEVEL=info
"@

Set-Content -Path "frontend\.env.example" -Value $FrontendEnvContent -Encoding ASCII
Write-Host "[OK] frontend .env.example created" -ForegroundColor Green

# Root .env.example
Write-Host "[*] Creating root .env.example..." -ForegroundColor Yellow
$RootEnvContent = @"
PROJECT_NAME=career-guidance-system
ENVIRONMENT=development
"@

Set-Content -Path ".env.example" -Value $RootEnvContent -Encoding ASCII
Write-Host "[OK] root .env.example created" -ForegroundColor Green

# .gitignore
Write-Host "[*] Creating .gitignore..." -ForegroundColor Yellow
$GitignoreContent = @"
.env
.env.local
.env.*.local
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
build/
develop-eggs/
dist/
downloads/
eggs/
.eggs/
lib/
lib64/
parts/
sdist/
var/
wheels/
*.egg-info/
.installed.cfg
*.egg
.pytest_cache/
.coverage
htmlcov/
node_modules/
npm-debug.log
yarn-error.log
dist/
.next/
.vscode/
.idea/
*.swp
*.swo
*~
.DS_Store
logs/
*.log
*.db
*.sqlite
*.sqlite3
.dockerignore
Thumbs.db
*.pkl
*.pth
*.h5
ml-models/pretrained/*
!ml-models/pretrained/.gitkeep
"@

Set-Content -Path ".gitignore" -Value $GitignoreContent -Encoding ASCII
Write-Host "[OK] .gitignore created" -ForegroundColor Green

# README.md
Write-Host "[*] Creating README.md..." -ForegroundColor Yellow
$ReadmeContent = @"
# Career Guidance System - Agentic AI

Advanced AI-powered career guidance system using agents, NLP, and machine learning.

## Features

- Multi-agent AI system for career guidance
- Interactive chat interface with history
- Personalized recommendations
- NLP-based understanding
- RAG for real-time job/skill data
- XAI explanations for transparency
- Career path planning
- Personalized learning suggestions

## Tech Stack

Backend: FastAPI, Python, PostgreSQL, MongoDB
Frontend: React, Next.js, Tailwind CSS
AI/ML: LangChain, PyTorch, XGBoost, Transformers
Infrastructure: Docker, Kubernetes, GCP/AWS

## Quick Start

Prerequisites:
- Docker & Docker Compose
- Python 3.11+
- Node.js 18+

Installation:

  git clone <repo-url>
  cd career-guidance-system
  cp backend/.env.example backend/.env
  cp frontend/.env.example frontend/.env

Run with Docker:

  docker-compose up --build

Access:
- Frontend: http://localhost:3000
- Backend API: http://localhost:8000
- API Docs: http://localhost:8000/docs

## Project Structure

career-guidance-system/
- backend/              - FastAPI backend
- frontend/            - React frontend
- ml-models/           - ML training
- config/              - Configuration files
- kubernetes/          - K8s manifests
- .github/             - CI/CD workflows
- docker-compose.yml   - Docker Compose file

## License

MIT License
"@

Set-Content -Path "README.md" -Value $ReadmeContent -Encoding ASCII
Write-Host "[OK] README.md created" -ForegroundColor Green

# Dockerfile - Backend
Write-Host "[*] Creating Dockerfile files..." -ForegroundColor Yellow
$BackendDockerfileContent = @"
FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y build-essential curl && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
"@

Set-Content -Path "backend\Dockerfile" -Value $BackendDockerfileContent -Encoding ASCII
Write-Host "[OK] backend Dockerfile created" -ForegroundColor Green

# Dockerfile - Frontend
$FrontendDockerfileContent = @"
FROM node:20-alpine as builder

WORKDIR /app

COPY package*.json ./

RUN npm install

COPY . .

RUN npm run build

FROM node:20-alpine

WORKDIR /app

RUN npm install -g serve

COPY --from=builder /app/dist ./dist

EXPOSE 3000

CMD ["serve", "-s", "dist", "-l", "3000"]
"@

Set-Content -Path "frontend\Dockerfile" -Value $FrontendDockerfileContent -Encoding ASCII
Write-Host "[OK] frontend Dockerfile created" -ForegroundColor Green

# .dockerignore
Write-Host "[*] Creating .dockerignore files..." -ForegroundColor Yellow
$DockerignoreContent = @"
__pycache__
*.pyc
*.pyo
.env
.git
.gitignore
.vscode
.idea
node_modules
npm-debug.log
yarn-error.log
dist
build
.pytest_cache
.coverage
"@

Set-Content -Path "backend\.dockerignore" -Value $DockerignoreContent -Encoding ASCII
Set-Content -Path "frontend\.dockerignore" -Value $DockerignoreContent -Encoding ASCII
Write-Host "[OK] .dockerignore files created" -ForegroundColor Green

# docker-compose.yml
Write-Host "[*] Creating docker-compose.yml..." -ForegroundColor Yellow
$DockerComposeContent = @"
version: '3.8'

services:
  postgres:
    image: postgres:16-alpine
    container_name: career_postgres
    environment:
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: rahulpg
      POSTGRES_DB: postgres
    volumes:
      - postgres_data:/var/lib/postgresql/data
    ports:
      - "5432:5432"
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U career_user"]
      interval: 10s
      timeout: 5s
      retries: 5

  mongodb:
    image: mongo:7.0
    container_name: career_mongodb
    environment:
      MONGO_INITDB_DATABASE: career_chat_history
    volumes:
      - mongodb_data:/data/db
    ports:
      - "27017:27017"
    healthcheck:
      test: ["CMD", "mongosh", "--eval", "db.adminCommand('ping')"]
      interval: 10s
      timeout: 5s
      retries: 5

  redis:
    image: redis:7-alpine
    container_name: career_redis
    ports:
      - "6379:6379"
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 5s
      retries: 5

  backend:
    build:
      context: ./backend
      dockerfile: Dockerfile
    container_name: career_backend
    environment:
      - ENV=development
      - DATABASE_URL=postgresql://postgres:rahulpg@localhost:5432/postgres
      - MONGODB_URL=mongodb://mongodb:27017
      - REDIS_URL=redis://redis:6379/0
    ports:
      - "8000:8000"
    depends_on:
      postgres:
        condition: service_healthy
      mongodb:
        condition: service_healthy
      redis:
        condition: service_healthy
    volumes:
      - ./backend:/app
    command: uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

  frontend:
    build:
      context: ./frontend
      dockerfile: Dockerfile
    container_name: career_frontend
    ports:
      - "3000:3000"
    depends_on:
      - backend
    volumes:
      - ./frontend:/app
      - /app/node_modules
    environment:
      - VITE_API_URL=http://localhost:8000/api/v1

volumes:
  postgres_data:
  mongodb_data:

networks:
  default:
    name: career_network
"@

Set-Content -Path "docker-compose.yml" -Value $DockerComposeContent -Encoding ASCII
Write-Host "[OK] docker-compose.yml created" -ForegroundColor Green

Write-Host ""

# ===== SUMMARY =====
Write-Host "================================================" -ForegroundColor Green
Write-Host "   PROJECT SETUP COMPLETE!" -ForegroundColor Green
Write-Host "================================================" -ForegroundColor Green
Write-Host ""

Write-Host "Project Location:" -ForegroundColor Yellow
Write-Host "   $ProjectPath" -ForegroundColor Cyan
Write-Host ""

Write-Host "Statistics:" -ForegroundColor Yellow
Write-Host "   Backend Python files:    $BackendPyFileCount" -ForegroundColor Gray
Write-Host "   Frontend files:          $FrontendFileCount" -ForegroundColor Gray
Write-Host "   ML files:                $MLFileCount" -ForegroundColor Gray
Write-Host "   Config files:            $ConfigFileCount" -ForegroundColor Gray
Write-Host ""

Write-Host "Next Steps:" -ForegroundColor Yellow
Write-Host "   1. cd career-guidance-system" -ForegroundColor White
Write-Host "   2. Update backend\.env.example to backend\.env" -ForegroundColor White
Write-Host "   3. Update frontend\.env.example to frontend\.env" -ForegroundColor White
Write-Host "   4. Run: docker-compose up --build" -ForegroundColor White
Write-Host ""

Write-Host "Directory Structure:" -ForegroundColor Yellow
Write-Host "   OK  backend/          - FastAPI backend application" -ForegroundColor Gray
Write-Host "   OK  frontend/         - React frontend application" -ForegroundColor Gray
Write-Host "   OK  ml-models/        - ML model training" -ForegroundColor Gray
Write-Host "   OK  config/           - Configuration files" -ForegroundColor Gray
Write-Host "   OK  kubernetes/       - K8s manifests" -ForegroundColor Gray
Write-Host "   OK  .github/          - CI/CD workflows" -ForegroundColor Gray
Write-Host "   OK  scripts/          - Utility scripts" -ForegroundColor Gray
Write-Host ""

Write-Host "Access Points (after docker-compose up):" -ForegroundColor Yellow
Write-Host "   Frontend:     http://localhost:3000" -ForegroundColor Cyan
Write-Host "   Backend API:  http://localhost:8000" -ForegroundColor Cyan
Write-Host "   API Docs:     http://localhost:8000/docs" -ForegroundColor Cyan
Write-Host "   PostgreSQL:   localhost:5432" -ForegroundColor Cyan
Write-Host "   MongoDB:      localhost:27017" -ForegroundColor Cyan
Write-Host "   Redis:        localhost:6379" -ForegroundColor Cyan
Write-Host ""

Write-Host "Create ZIP File:" -ForegroundColor Yellow
Write-Host "   Compress-Archive -Path career-guidance-system -DestinationPath career-guidance-system.zip" -ForegroundColor Cyan
Write-Host ""

Write-Host "================================================" -ForegroundColor Green
Write-Host "   Happy Coding!" -ForegroundColor Green
Write-Host "================================================" -ForegroundColor Green
Write-Host ""

Read-Host "Press Enter to exit"