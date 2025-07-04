package web

import (
	"embed"
	"html/template"
	"io/fs"
	"log"
)

//go:embed static/* templates/*
var Assets embed.FS

var Templates *template.Template

func init() {
	var err error
	Templates = template.New("")

	// Check if templates directory exists in embedded files
	entries, err := fs.ReadDir(Assets, "templates")
	if err != nil {
		log.Printf("ERROR: Cannot read templates directory: %v", err)
		Templates = template.Must(template.New("fallback").Parse(fallbackTemplate))
		return
	}

	log.Printf("Found %d template files", len(entries))
	for _, entry := range entries {
		log.Printf("  - %s", entry.Name())
	}

	// Parse templates with proper error handling
	Templates, err = Templates.ParseFS(Assets, "templates/*.html")
	if err != nil {
		log.Printf("ERROR: Failed to parse templates: %v", err)
		Templates = template.Must(template.New("fallback").Parse(fallbackTemplate))
	} else {
		log.Printf("✅ Templates parsed successfully")
		// List all parsed templates
		for _, tmpl := range Templates.Templates() {
			log.Printf("  Parsed template: %s", tmpl.Name())
		}
	}
}

const fallbackTemplate = `<!DOCTYPE html>
<html><head><title>{{.Title}}</title></head>
<body>
<h1>Trivia Service</h1>
<p>Templates are loading. Please ensure all template files are in place.</p>
<p>Error: {{.Error}}</p>
</body></html>`

// GetStaticFS returns the static files filesystem
func GetStaticFS() fs.FS {
	staticFS, err := fs.Sub(Assets, "static")
	if err != nil {
		log.Printf("Warning: Could not create static filesystem: %v", err)
		return nil
	}
	return staticFS
}
