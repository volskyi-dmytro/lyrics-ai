# 🎵 Lyrics AI - Song Meaning Summarizer

> An intelligent web application that analyzes song lyrics and generates AI-powered artwork using cutting-edge machine learning technologies.

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)
[![Docker](https://img.shields.io/badge/Docker-Ready-blue?logo=docker)](https://www.docker.com/)
[![OpenAI](https://img.shields.io/badge/OpenAI-GPT--4o--mini%20%7C%20DALL--E--3-green)](https://openai.com/)
[![Genius API](https://img.shields.io/badge/Genius-API-yellow)](https://genius.com/)

## ✨ Features

### 🎯 Core Functionality
- **Real-time Lyrics Fetching** from Genius API
- **AI-Powered Analysis** using OpenAI GPT-4o-mini
- **Multilingual Support** (English & Ukrainian)
- **AI Artwork Generation** with DALL-E 3
- **10+ Artistic Styles** (vintage, psychedelic, minimalist, etc.)
- **Scrollable Content** for detailed analyses

### 🎨 AI-Generated Artwork Styles
- 🎭 **Album Cover** - Professional music industry style
- 🎬 **Cinematic** - Movie poster aesthetics
- 🎨 **Watercolor** - Soft artistic paintings
- 🔥 **Grunge** - Distressed textures and raw energy
- ⚪ **Minimalist** - Clean, modern design
- 📻 **Vintage** - Retro poster style
- 🌀 **Psychedelic** - Vibrant, surreal art
- 🌑 **Dark** - Moody atmospheric themes
- ☀️ **Bright** - Colorful, energetic designs
- 🎪 **Abstract** - Creative interpretations

## 🚀 Quick Start

### Prerequisites
- Docker & Docker Compose
- OpenAI API Key
- Genius API Token

### Installation

1. **Clone the repository**
```bash
git clone git@github.com:volskyi-dmytro/lyrics-ai.git
cd lyrics-ai
```

2. **Configure environment variables**
```bash
cp .env.example .env
# Edit .env with your API keys:
# OPENAI_API_KEY=your_openai_api_key_here
# GENIUS_API_TOKEN=your_genius_api_token_here
```

3. **Start the application**
```bash
docker-compose up -d
```

4. **Access the application**
- Open your browser to `http://localhost:8080`
- Start analyzing songs! 🎵

## 🏗️ Architecture

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   Frontend      │    │   Java API       │    │   Python AI     │
│   (HTML/JS)     │◄──►│   (Spring Boot)  │◄──►│   (FastAPI)     │
│   Port: 8080    │    │   Port: 8080     │    │   Port: 8000    │
└─────────────────┘    └──────────────────┘    └─────────────────┘
                                │                        │
                                │                        │
                       ┌─────────────────┐    ┌─────────────────┐
                       │   Static Files  │    │   External APIs │
                       │   (CSS/HTML)    │    │   • OpenAI      │
                       │                 │    │   • Genius      │
                       └─────────────────┘    └─────────────────┘
```

### Technology Stack

#### Frontend
- **HTML5/CSS3** - Modern responsive design
- **Vanilla JavaScript** - Clean, dependency-free code
- **Dark Theme** - Beautiful UI with gradient backgrounds

#### Backend Services
- **Java API (Spring Boot 3.3.2)**
  - RESTful API gateway
  - Request validation
  - Error handling
  - Static file serving

- **Python AI Service (FastAPI)**
  - Lyrics fetching from Genius API
  - AI text analysis with GPT-4o-mini
  - Image generation with DALL-E 3
  - Multilingual processing

#### Infrastructure
- **Docker & Docker Compose** - Containerized deployment
- **Health Checks** - Service monitoring
- **Logging** - Comprehensive error tracking

## 📋 API Reference

### Analyze Song
Analyzes a song's lyrics and generates artwork.

```http
POST /api/analyze
Content-Type: application/json

{
  "artist": "Queen",
  "title": "Bohemian Rhapsody",
  "style": "vintage",
  "language": "uk"
}
```

**Response:**
```json
{
  "summary": "Detailed song analysis...",
  "imageUrl": "https://oaidalleapiprodscus.blob.core.windows.net/..."
}
```

### Parameters
- `artist` (required) - Artist name
- `title` (required) - Song title
- `style` (optional) - Artwork style (default: "album cover")
- `language` (optional) - Summary language: "en" or "uk" (default: "en")

## 🔧 Configuration

### Environment Variables

Create a `.env` file in the project root:

```env
# OpenAI Configuration
OPENAI_API_KEY=sk-proj-your-openai-api-key-here

# Genius API Configuration
GENIUS_API_TOKEN=your-genius-api-token-here

# Optional: Custom base URLs
AI_BASE_URL=http://localhost:8000
```

### Getting API Keys

#### OpenAI API Key
1. Visit [OpenAI Platform](https://platform.openai.com/)
2. Create an account and navigate to API keys
3. Generate a new API key
4. Add credits to your account

#### Genius API Token
1. Visit [Genius API](https://genius.com/api-clients)
2. Create a new API client
3. Generate an access token
4. Copy the Client Access Token

## 🐳 Docker Configuration

The application uses multi-stage Docker builds for optimization:

- **Python Service**: Lightweight FastAPI container
- **Java Service**: Optimized Spring Boot container
- **Health Checks**: Automatic service monitoring
- **Dependencies**: Managed with Docker Compose

## 🔒 Security Features

- **Environment Variable Protection** - Sensitive data in `.env` files
- **Input Sanitization** - Unicode normalization and validation
- **Error Handling** - Graceful degradation without exposing internals
- **Rate Limiting Ready** - Architecture supports rate limiting
- **HTTPS Ready** - Can be easily configured for SSL/TLS

## 📊 Performance

- **Fast Response Times** - Optimized API calls and caching
- **Concurrent Processing** - Async/await patterns throughout
- **Lightweight Containers** - Minimal resource usage
- **Scalable Architecture** - Microservices design

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📝 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- **OpenAI** for GPT-4o-mini and DALL-E 3 APIs
- **Genius** for lyrics data
- **Spring Boot & FastAPI** communities
- **Docker** for containerization

## 📞 Support

If you encounter any issues or have questions:

1. Check the [Issues](https://github.com/volskyi-dmytro/lyrics-ai/issues) page
2. Create a new issue with detailed information
3. Follow the issue template for faster resolution

---

**Made with ❤️ and AI** - Transform any song into visual art and deep meaning analysis.