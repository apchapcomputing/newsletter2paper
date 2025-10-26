package pdf

import (
	"fmt"
	"html"
	"path/filepath"
	"strings"
	"time"

	art "newsletter2newspaper/internal/article"
)

// AssembleHTML builds the complete HTML document with header, TOC, and article sections.
func AssembleHTML(articles []*art.Article, title string) (string, error) {
	var sb strings.Builder

	// Determine absolute path to CSS for file:// reference
	cssPath, _ := filepath.Abs("styles/default.css")

	// HTML header
	sb.WriteString("<!DOCTYPE html>\n<html lang=\"en\">\n<head>\n")
	sb.WriteString("  <meta charset=\"UTF-8\">\n")
	sb.WriteString("  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\">\n")
	sb.WriteString(fmt.Sprintf("  <title>%s</title>\n", html.EscapeString(title)))
	sb.WriteString(fmt.Sprintf("  <link rel=\"stylesheet\" href=\"file://%s\">\n", cssPath))
	sb.WriteString("</head>\n<body>\n")

	// Header section
	sb.WriteString("<div class=\"pdf-header\">\n")
	sb.WriteString(fmt.Sprintf("  <h1>%s</h1>\n", html.EscapeString(title)))
	sb.WriteString(fmt.Sprintf("  <p class=\"date\">%s</p>\n", time.Now().Format("Monday, January 2, 2006")))
	sb.WriteString("</div>\n\n")

	// Table of Contents
	sb.WriteString("<div class=\"toc\">\n")
	sb.WriteString("  <h2>Table of Contents</h2>\n")
	sb.WriteString("  <ul>\n")
	for i, a := range articles {
		sb.WriteString(fmt.Sprintf("    <li><a href=\"#article-%d\">%s</a>", i+1, html.EscapeString(a.Title)))
		if a.Author != "" {
			sb.WriteString(fmt.Sprintf(" <span class=\"toc-author\">by %s</span>", html.EscapeString(a.Author)))
		}
		if a.Publication != "" {
			sb.WriteString(fmt.Sprintf(" <span class=\"toc-publication\">— %s</span>", html.EscapeString(a.Publication)))
		}
		sb.WriteString("</li>\n")
	}
	sb.WriteString("  </ul>\n")
	sb.WriteString("</div>\n\n")

	// Articles
	for i, a := range articles {
		sb.WriteString(renderArticle(a, i+1))
	}

	// Close HTML
	sb.WriteString("</body>\n</html>")

	return sb.String(), nil
}

// renderArticle generates the HTML for a single article section.
func renderArticle(a *art.Article, num int) string {
	var sb strings.Builder

	sb.WriteString(fmt.Sprintf("<div class=\"article\" id=\"article-%d\">\n", num))

	// Article header
	sb.WriteString("  <div class=\"article-header\">\n")
	sb.WriteString(fmt.Sprintf("    <h2 class=\"article-title\">%s</h2>\n", html.EscapeString(a.Title)))

	if a.Subtitle != "" {
		sb.WriteString(fmt.Sprintf("    <h3 class=\"article-subtitle\">%s</h3>\n", html.EscapeString(a.Subtitle)))
	}

	// Metadata line
	meta := []string{}
	if a.Author != "" {
		meta = append(meta, fmt.Sprintf("By %s", html.EscapeString(a.Author)))
	}
	if a.Publication != "" {
		meta = append(meta, html.EscapeString(a.Publication))
	}
	if !a.PubDate.IsZero() {
		meta = append(meta, a.PubDate.Format("January 2, 2006"))
	}
	if len(meta) > 0 {
		sb.WriteString(fmt.Sprintf("    <p class=\"article-meta\">%s</p>\n", strings.Join(meta, " • ")))
	}

	sb.WriteString("  </div>\n\n")

	// Article content (already HTML)
	sb.WriteString("  <div class=\"article-content\">\n")
	sb.WriteString(a.Content) // raw HTML from fetch
	sb.WriteString("\n  </div>\n")

	sb.WriteString("</div>\n\n")

	return sb.String()
}
