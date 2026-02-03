package article

import (
	"encoding/json"
	"fmt"
	"io"
	"os"
	"time"
)

// ArticleInput represents the JSON format that FastAPI will send to the Go CLI.
// It can contain either a content_url (to be fetched) or raw HTML content.
type ArticleInput struct {
	Title         string `json:"title"`
	Subtitle      string `json:"subtitle,omitempty"`
	Author        string `json:"author,omitempty"`
	Publication   string `json:"publication,omitempty"`
	DatePublished string `json:"date_published,omitempty"` // ISO 8601 format
	ContentURL    string `json:"content_url,omitempty"`    // URL to fetch content from
	Content       string `json:"content,omitempty"`        // Or raw HTML content
	PublicationID string `json:"publication_id,omitempty"`
	RemoveImages  bool   `json:"remove_images,omitempty"` // Per-publication image removal setting
}

// IssueInput represents the full payload with issue metadata and articles.
type IssueInput struct {
	IssueID          string         `json:"issue_id"`
	IssueTitle       string         `json:"issue_title"`
	IssueDescription string         `json:"issue_description,omitempty"`
	Articles         []ArticleInput `json:"articles"`
	LayoutType       string         `json:"layout_type,omitempty"` // "newspaper" or "essay"
}

// LoadArticlesFromJSON reads an IssueInput JSON file and returns the parsed data.
func LoadArticlesFromJSON(path string) (*IssueInput, error) {
	f, err := os.Open(path)
	if err != nil {
		return nil, fmt.Errorf("open file: %w", err)
	}
	defer f.Close()

	return ParseArticlesJSON(f)
}

// ParseArticlesJSON parses an IssueInput from a reader (for stdin support).
func ParseArticlesJSON(r io.Reader) (*IssueInput, error) {
	var input IssueInput
	decoder := json.NewDecoder(r)
	if err := decoder.Decode(&input); err != nil {
		return nil, fmt.Errorf("parse json: %w", err)
	}

	// Validate
	if len(input.Articles) == 0 {
		return nil, fmt.Errorf("no articles provided in JSON")
	}

	return &input, nil
}

// ToArticle converts an ArticleInput to an Article struct.
// If ContentURL is provided but Content is empty, the caller should fetch it.
func (ai *ArticleInput) ToArticle() *Article {
	a := &Article{
		Title:        ai.Title,
		Subtitle:     ai.Subtitle,
		Author:       ai.Author,
		Publication:  ai.Publication,
		Link:         ai.ContentURL,
		Content:      ai.Content,
		RemoveImages: ai.RemoveImages,
	}

	// Parse date if provided
	if ai.DatePublished != "" {
		// Try multiple date formats
		formats := []string{
			time.RFC3339,
			time.RFC3339Nano,
			"2006-01-02T15:04:05Z07:00",
			"2006-01-02T15:04:05",
			"2006-01-02",
		}

		for _, format := range formats {
			if t, err := time.Parse(format, ai.DatePublished); err == nil {
				a.PubDate = t
				break
			}
		}
	}

	return a
}
