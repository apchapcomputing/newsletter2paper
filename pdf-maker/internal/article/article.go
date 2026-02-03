package article

import "time"

// Article represents a single newsletter/article unit extracted from a source page.
// Content holds ONLY the inner HTML of the main article body (div.available-content per Substack pages).
type Article struct {
	Title        string
	Subtitle     string
	Author       string
	Publication  string
	PubDate      time.Time
	Link         string
	Content      string // raw or cleaned HTML (body only)
	RemoveImages bool   // Whether to remove images from this article's content
}
