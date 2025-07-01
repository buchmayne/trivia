package main

import (
	"fmt"
	"log"
	"net/http"

	"github.com/gorilla/websocket"
)

var upgrader = websocket.Upgrader{
	CheckOrigin: func(r *http.Request) bool {
		return true
	},
}

// Message types that will be sent over WebSocket
type Message struct {
	Type string      `json:"type"`
	Data interface{} `json:"data"`
	From string      `json:"from,omitempty"`
}

// Client represents a WebSocket connection
type Client struct {
	ID   string
	Conn *websocket.Conn
	Hub  *Hub
	Send chan Message
}

// Hub maintains the set of active clients and broadcasts messages
type Hub struct {
	Clients    map[*Client]bool
	Broadcast  chan Message
	Register   chan *Client
	Unregister chan *Client
}

func NewHub() *Hub {
	return &Hub{
		Clients:    make(map[*Client]bool),
		Broadcast:  make(chan Message),
		Register:   make(chan *Client),
		Unregister: make(chan *Client),
	}
}

func (h *Hub) Run() {
	for {
		select {
		case client := <-h.Register:
			h.Clients[client] = true
			fmt.Printf("✅ Client %s connected (total: %d)\n", client.ID, len(h.Clients))

			// Send welcome message to new client
			welcomeMsg := Message{
				Type: "welcome",
				Data: map[string]interface{}{
					"message": "Connected to trivia session hub!",
					"clients": len(h.Clients),
				},
			}
			select {
			case client.Send <- welcomeMsg:
			default:
				close(client.Send)
				delete(h.Clients, client)
			}

			// Notify all clients about new connection
			h.broadcastClientUpdate()

		case client := <-h.Unregister:
			if _, ok := h.Clients[client]; ok {
				delete(h.Clients, client)
				close(client.Send)
				fmt.Printf("❌ Client %s disconnected (total: %d)\n", client.ID, len(h.Clients))
				h.broadcastClientUpdate()
			}

		case message := <-h.Broadcast:
			fmt.Printf("📢 Broadcasting %s message to %d clients\n", message.Type, len(h.Clients))
			for client := range h.Clients {
				select {
				case client.Send <- message:
				default:
					close(client.Send)
					delete(h.Clients, client)
				}
			}
		}
	}
}

func (h *Hub) broadcastClientUpdate() {
	clientList := make([]string, 0, len(h.Clients))
	for client := range h.Clients {
		clientList = append(clientList, client.ID)
	}

	message := Message{
		Type: "client_update",
		Data: map[string]interface{}{
			"count":   len(h.Clients),
			"clients": clientList,
		},
	}

	select {
	case h.Broadcast <- message:
	default:
	}
}

func (c *Client) ReadPump() {
	defer func() {
		c.Hub.Unregister <- c
		c.Conn.Close()
	}()

	for {
		var msg Message
		err := c.Conn.ReadJSON(&msg)
		if err != nil {
			if websocket.IsUnexpectedCloseError(err, websocket.CloseGoingAway, websocket.CloseAbnormalClosure) {
				log.Printf("WebSocket error: %v", err)
			}
			break
		}

		fmt.Printf("📨 Message from %s: %s\n", c.ID, msg.Type)

		// Add sender info and broadcast
		msg.From = c.ID
		c.Hub.Broadcast <- msg
	}
}

func (c *Client) WritePump() {
	defer c.Conn.Close()

	for {
		select {
		case message, ok := <-c.Send:
			if !ok {
				c.Conn.WriteMessage(websocket.CloseMessage, []byte{})
				return
			}

			if err := c.Conn.WriteJSON(message); err != nil {
				log.Printf("Failed to write message: %v", err)
				return
			}
		}
	}
}

func main() {
	fmt.Println("🎯 Starting Trivia Session Hub...")

	hub := NewHub()
	go hub.Run()

	http.HandleFunc("/", homeHandler)
	http.HandleFunc("/ws", func(w http.ResponseWriter, r *http.Request) {
		websocketHandler(hub, w, r)
	})

	port := ":8080"
	fmt.Printf("Hub running at http://localhost%s\n", port)
	fmt.Println("Open multiple browser tabs to test multi-client support!")

	log.Fatal(http.ListenAndServe(port, nil))
}

func homeHandler(w http.ResponseWriter, r *http.Request) {
	html := `<!DOCTYPE html>
<html>
<head>
    <title>Trivia Session Hub Test</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; }
        #messages { border: 1px solid #ccc; height: 300px; overflow-y: scroll; padding: 10px; margin: 10px 0; }
        .message { margin: 5px 0; }
        .from-me { color: blue; }
        .from-other { color: green; }
        .system { color: red; font-style: italic; }
        input[type="text"] { width: 300px; padding: 5px; }
        button { padding: 5px 10px; }
    </style>
</head>
<body>
    <h1>🎯 Trivia Session Hub</h1>
    <div>
        <label>Your Name: <input type="text" id="clientName" value="Team1" /></label>
        <button onclick="connect()">Connect</button>
        <button onclick="disconnect()">Disconnect</button>
    </div>
    <div id="status">Not connected</div>
    <div id="clientList"></div>
    <div>
        <input type="text" id="messageInput" placeholder="Type a message..." disabled />
        <button onclick="sendMessage()" disabled id="sendBtn">Send</button>
    </div>
    <div id="messages"></div>

    <script>
        let ws = null;
        let clientName = '';

        function connect() {
            clientName = document.getElementById('clientName').value || 'Anonymous';
            ws = new WebSocket('ws://localhost:8080/ws?name=' + encodeURIComponent(clientName));
            
            ws.onopen = function() {
                document.getElementById('status').textContent = '✅ Connected as ' + clientName;
                document.getElementById('messageInput').disabled = false;
                document.getElementById('sendBtn').disabled = false;
            };

            ws.onmessage = function(event) {
                const msg = JSON.parse(event.data);
                handleMessage(msg);
            };

            ws.onclose = function() {
                document.getElementById('status').textContent = '❌ Disconnected';
                document.getElementById('messageInput').disabled = true;
                document.getElementById('sendBtn').disabled = true;
            };
        }

        function disconnect() {
            if (ws) {
                ws.close();
            }
        }

        function handleMessage(msg) {
            const messages = document.getElementById('messages');
            const div = document.createElement('div');
            div.className = 'message';
            
            if (msg.type === 'welcome') {
                div.className += ' system';
                div.textContent = '🎉 ' + msg.data.message + ' (' + msg.data.clients + ' clients connected)';
            } else if (msg.type === 'client_update') {
                div.className += ' system';
                div.textContent = '👥 Clients online: ' + msg.data.clients.join(', ') + ' (' + msg.data.count + ' total)';
                document.getElementById('clientList').textContent = 'Online: ' + msg.data.clients.join(', ');
            } else if (msg.type === 'chat') {
                const className = msg.from === clientName ? 'from-me' : 'from-other';
                div.className += ' ' + className;
                div.textContent = msg.from + ': ' + msg.data;
            }
            
            messages.appendChild(div);
            messages.scrollTop = messages.scrollHeight;
        }

        function sendMessage() {
            const input = document.getElementById('messageInput');
            if (ws && input.value.trim() !== '') {
                const msg = {
                    type: 'chat',
                    data: input.value
                };
                ws.send(JSON.stringify(msg));
                input.value = '';
            }
        }

        document.getElementById('messageInput').addEventListener('keypress', function(e) {
            if (e.key === 'Enter') {
                sendMessage();
            }
        });
    </script>
</body>
</html>`

	w.Header().Set("Content-Type", "text/html")
	fmt.Fprint(w, html)
}

func websocketHandler(hub *Hub, w http.ResponseWriter, r *http.Request) {
	conn, err := upgrader.Upgrade(w, r, nil)
	if err != nil {
		log.Printf("Failed to upgrade connection: %v", err)
		return
	}

	// Get client name from query parameter
	clientName := r.URL.Query().Get("name")
	if clientName == "" {
		clientName = fmt.Sprintf("Client-%s", r.RemoteAddr)
	}

	client := &Client{
		ID:   clientName,
		Conn: conn,
		Hub:  hub,
		Send: make(chan Message, 256),
	}

	client.Hub.Register <- client

	// Start goroutines for reading and writing
	go client.WritePump()
	go client.ReadPump()
}
