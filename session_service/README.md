# Refactored Session Service Setup

## Directory Structure

Create this folder structure in your session service:

```
session_service/
├── cmd/server/
│   └── main.go                    # Main server file
├── pkg/django/
│   └── client.go                  # Django API client
├── templates/
│   ├── base.html                  # Base template
│   ├── home.html                  # Homepage
│   ├── host.html                  # Host dashboard
│   ├── host_session.html          # Active host session
│   ├── team_join.html             # Team join page
│   ├── team_session.html          # Active team session
│   └── error.html                 # Error page
├── static/
│   ├── style.css                  # Main stylesheet
│   ├── app.js                     # Core JavaScript
│   ├── host.js                    # Host-specific JS
│   └── team.js                    # Team-specific JS
└── go.mod                         # Go module file
```

## Setup Steps

1. **Create the directory structure** as shown above

2. **Copy the files** from the artifacts into their respective locations

3. **Update your go.mod** to include required dependencies:
```go
module session_service

go 1.21

require (
    github.com/gorilla/mux v1.8.0
    github.com/gorilla/websocket v1.5.0
)
```

4. **Install dependencies**:
```bash
cd session_service
go mod tidy
```

5. **Build and run**:
```bash
go run cmd/server/main.go
```

## Key Improvements

### 🎯 **Template System**
- Clean separation of HTML from Go code
- Reusable base template with shared layout
- Embedded templates for single-binary deployment

### 🎨 **Static Assets**
- Proper CSS architecture with modern design
- Modular JavaScript with class-based organization
- Embedded static files for easy deployment

### 🚀 **Better Development Experience**
- Hot-reloadable templates (restart server to see changes)
- Cleaner code organization
- Better error handling and user feedback

### 📱 **Responsive Design**
- Mobile-friendly interface
- Modern CSS with custom properties
- Accessible color scheme and typography

### 🔌 **WebSocket Integration**
- Automatic reconnection on disconnect
- Real-time team updates
- Connection status indicators

## New Features

### **Host Dashboard**
- Visual session code display with copy button
- Real-time team tracking
- Game state management
- Question display with correct answers

### **Team Interface**
- Session validation before joining
- Waiting room with team list
- Interactive answer selection
- Answer submission confirmation

### **Shared Features**
- Connection status indicators
- Real-time notifications
- Error handling with user-friendly messages
- Session code auto-formatting

## Usage

1. **Start the service**: `go run cmd/server/main.go`
2. **Navigate to**: `http://localhost:8080`
3. **Host a game**: Click "Host a Game" and create session
4. **Join as team**: Click "Join a Game" and enter session code
5. **Play**: Host starts game, teams answer questions in real-time

## Integration with Django

The refactored service maintains full integration with your Django backend:

### **API Endpoints Used**
- `GET /quiz/api/games/{id}/questions/` - Fetch game questions
- `POST /quiz/api/sessions/create/` - Create session record
- `POST /quiz/api/answers/submit/` - Submit team answers
- `PATCH /quiz/api/sessions/{id}/status/` - Update session status

### **Data Flow**
1. Go service fetches questions from Django on session creation
2. WebSocket handles real-time gameplay
3. Answers are submitted back to Django for persistence
4. Session state synchronized between services

## Development Workflow

### **Quick Iteration**
1. Edit templates/CSS/JS files
2. Restart Go server (`Ctrl+C`, then `go run cmd/server/main.go`)
3. Refresh browser to see changes
4. No need to rebuild for template/static changes

### **Adding New Features**
- **New pages**: Add template + route handler
- **New styles**: Edit `static/style.css`
- **New interactions**: Add to appropriate JS file
- **New API calls**: Extend Django client

### **Debugging**
- Check browser console for WebSocket messages
- Server logs show session creation and connections
- Django logs show API interactions

## Testing the Refactored Service

### **Basic Flow Test**
1. Start Django: `python manage.py runserver`
2. Start Go service: `go run cmd/server/main.go`
3. Open `http://localhost:8080` in multiple browser tabs
4. Create session in one tab (host)
5. Join session in other tabs (teams)
6. Test real-time communication

### **Features to Verify**
- ✅ Session creation with game selection
- ✅ Team joining with validation
- ✅ WebSocket connection status
- ✅ Real-time team list updates
- ✅ Question display and answer submission
- ✅ Session code copying
- ✅ Responsive design on mobile

## Next Steps

### **Immediate Improvements**
1. **Add question images** - Enhance question display
2. **Implement scoring** - Show real-time scores
3. **Add game timer** - Time-limited questions
4. **Session history** - Track completed games

### **Production Considerations**
1. **Authentication** - Secure host access
2. **Rate limiting** - Prevent spam connections
3. **Monitoring** - Health checks and metrics
4. **Scaling** - Multiple server instances
5. **SSL/TLS** - Secure WebSocket connections

### **Advanced Features**
1. **Custom games** - Upload question sets
2. **Team management** - Persistent team profiles
3. **Spectator mode** - View-only access
4. **Game variants** - Different question types
5. **Analytics** - Detailed game statistics

## File Overview

### **Go Files**
- `main.go` - HTTP routes, WebSocket handling, session management
- `client.go` - Django API integration

### **Templates**
- `base.html` - Shared layout and navigation
- `home.html` - Landing page with feature overview
- `host.html` - Host session creation form
- `host_session.html` - Active host dashboard
- `team_join.html` - Team join form
- `team_session.html` - Team gameplay interface
- `error.html` - Error page template

### **JavaScript**
- `app.js` - Core WebSocket and utility functions
- `host.js` - Host-specific controls and session management
- `team.js` - Team answer submission and game flow

### **CSS**
- `style.css` - Complete responsive design system

This refactored structure gives you a much more maintainable and feature-rich trivia service that's ready for iterative development and production deployment.