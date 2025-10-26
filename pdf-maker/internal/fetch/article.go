package fetch

import (
	"bytes"
	"context"
	"crypto/sha1"
	"errors"
	"fmt"
	"io"
	"net/http"
	"net/url"
	"os"
	"path/filepath"
	"regexp"
	"strings"
	"time"

	"github.com/PuerkitoBio/goquery"
	art "pdf-maker/internal/article"
	"pdf-maker/internal/clean"
	"pdf-maker/internal/images"
)

// FetchAndSaveArticle downloads the HTML for the given article URL and saves it to disk.
// It returns the absolute path to the saved file.
// Behavior:
//   * Sets a reasonable timeout (15s) and custom User-Agent.
//   * Validates a 200 response code.
//   * Derives a filename from the last URL path segment, sanitized; falls back to a hash.
//   * Creates the output directory if missing.
//   * Writes raw HTML bytes with 0644 permissions.
// FetchArticle retrieves the page, parses fields, and returns a populated Article model.
// If imageDownloader is provided, it will download all images and rewrite URLs to local paths.
func FetchArticle(ctx context.Context, pageURL string) (*art.Article, []byte, error) {
	return FetchArticleWithImages(ctx, pageURL, nil)
}

// FetchArticleWithImages retrieves the page, parses fields, and optionally downloads images.
func FetchArticleWithImages(ctx context.Context, pageURL string, imageDownloader *images.Downloader) (*art.Article, []byte, error) {
    if pageURL == "" { return nil, nil, errors.New("empty url") }

    if _, ok := ctx.Deadline(); !ok {
        var cancel context.CancelFunc
        ctx, cancel = context.WithTimeout(ctx, 15*time.Second)
        defer cancel()
    }

    client := &http.Client{Timeout: 15 * time.Second}
    req, err := http.NewRequestWithContext(ctx, http.MethodGet, pageURL, nil)
    if err != nil { return nil, nil, fmt.Errorf("build request: %w", err) }
    req.Header.Set("User-Agent", "newsletter2newspaper-fetcher/0.1 (+https://example.com)")
    req.Header.Set("Accept", "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8")

    resp, err := client.Do(req)
    if err != nil { return nil, nil, fmt.Errorf("http get: %w", err) }
    defer resp.Body.Close()
    if resp.StatusCode != http.StatusOK { return nil, nil, fmt.Errorf("unexpected status %d", resp.StatusCode) }

    const maxSize = 20 * 1024 * 1024
    limited := &io.LimitedReader{R: resp.Body, N: maxSize + 1}
    raw, err := io.ReadAll(limited)
    if err != nil { return nil, nil, fmt.Errorf("read body: %w", err) }
    if limited.N <= 0 { return nil, nil, errors.New("article exceeds size limit (20MB)") }

    // Parse the document
    doc, err := goquery.NewDocumentFromReader(bytes.NewReader(raw))
    if err != nil { return nil, nil, fmt.Errorf("parse html: %w", err) }

    a := &art.Article{ Link: pageURL }

    // Title & Subtitle
    a.Title = strings.TrimSpace(doc.Find("h1.post-title.published").First().Text())
    a.Subtitle = strings.TrimSpace(doc.Find("h3.subtitle").First().Text())
    // Author & Publication via helpers (with fallbacks)
    a.Author = extractAuthor(doc)
    a.Publication = extractPublication(doc, pageURL)
    // PubDate extraction strategies (priority order): meta tag, time tag, byline text pattern
    if ts := doc.Find("meta[property='article:published_time']").AttrOr("content", ""); ts != "" {
        if t, e := time.Parse(time.RFC3339, ts); e == nil { a.PubDate = t }
    }
    if a.PubDate.IsZero() {
        if tEl := doc.Find("time").First(); tEl.Length() > 0 {
            if dt, ok := tEl.Attr("datetime"); ok { if t, e := time.Parse(time.RFC3339, dt); e == nil { a.PubDate = t } }
        }
    }
    if a.PubDate.IsZero() { // pattern search inside byline wrapper for formats like "Oct 09, 2025"
        if dateStr := findDateInByline(doc); dateStr != "" {
            if t, e := time.Parse("Jan 02, 2006", dateStr); e == nil { a.PubDate = t }
        }
    }

    // Content extraction
    if sel := doc.Find("div.available-content").First(); sel.Length() > 0 {
        if inner, e := sel.Html(); e == nil { a.Content = inner }
    }
    if a.Content == "" { // fallback
        if sel := doc.Find("div#entry").First(); sel.Length() > 0 { if inner, e := sel.Html(); e == nil { a.Content = inner } }
    }
    if a.Content == "" { a.Content = string(raw) } // ultimate fallback

    // Clean HTML content (remove subscription widgets, forms, format footnotes)
    cleaned, _, err := clean.CleanHTML(a.Content, false)
    if err == nil {
        a.Content = cleaned
    }
    // If cleaning fails, we keep the uncleaned content rather than failing the whole fetch

    // Download images and rewrite URLs if downloader is provided
    if imageDownloader != nil {
        processedContent, err := imageDownloader.ProcessHTML(a.Content)
        if err == nil {
            a.Content = processedContent
        } else {
            fmt.Fprintf(os.Stderr, "Warning: failed to process images for %s: %v\n", pageURL, err)
        }
    }

    return a, raw, nil
}

// FetchAndSaveArticle keeps backward compatibility: fetches article, saves content HTML, returns path.
func FetchAndSaveArticle(ctx context.Context, pageURL, outDir string) (string, error) {
    artc, _, err := FetchArticle(ctx, pageURL)
    if err != nil { return "", err }
    if outDir == "" { outDir = "." }
    filename := deriveFilename(pageURL)
    if err := os.MkdirAll(outDir, 0o755); err != nil { return "", fmt.Errorf("mkdir %s: %w", outDir, err) }
    absDir, err := filepath.Abs(outDir); if err != nil { return "", fmt.Errorf("abs dir: %w", err) }
    outPath := filepath.Join(absDir, filename)
    if err := os.WriteFile(outPath, []byte(artc.Content), 0o644); err != nil { return "", fmt.Errorf("write file: %w", err) }
    return outPath, nil
}

var trailingSlash = regexp.MustCompile(`/+$`)
var unsafeChars = regexp.MustCompile(`[^a-zA-Z0-9._-]+`)
var datePattern = regexp.MustCompile(`\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec) \d{2}, \d{4}\b`)

// findDateInByline searches the byline wrapper for a recognizable date string.
func findDateInByline(doc *goquery.Document) string {
    var found string
    doc.Find("div.byline-wrapper").First().Find("div,span").EachWithBreak(func(_ int, s *goquery.Selection) bool {
        text := strings.TrimSpace(s.Text())
        if text == "" { return true }
        if datePattern.MatchString(text) {
            found = datePattern.FindString(text)
            return false
        }
        return true
    })
    return found
}

// normalizeName title-cases a simple name string.
func normalizeName(name string) string {
    if name == "" { return name }
    parts := strings.Fields(name)
    for i, p := range parts {
        if len(p) == 0 { continue }
        parts[i] = strings.ToUpper(p[:1]) + strings.ToLower(p[1:])
    }
    return strings.Join(parts, " ")
}

// normalizePublication fixes curly apostrophes and trims whitespace.
func normalizePublication(s string) string {
    s = strings.TrimSpace(s)
    // Replace Unicode right single quotation mark with ASCII apostrophe.
    s = strings.ReplaceAll(s, "\u2019", "'")
    return s
}

// extractAuthor attempts multiple selectors / metadata sources to retrieve the author name.
func extractAuthor(doc *goquery.Document) string {
    // Primary: byline wrapper anchor
    if v := strings.TrimSpace(doc.Find("div.byline-wrapper a.pencraft").First().Text()); v != "" {
        return normalizeName(v)
    }
    // Fallback: any anchor with profile hover class
    if v := strings.TrimSpace(doc.Find(".profile-hover-card-target a").First().Text()); v != "" {
        return normalizeName(v)
    }
    // Meta author
    if v := strings.TrimSpace(doc.Find("meta[name='author']").AttrOr("content", "")); v != "" {
        return normalizeName(v)
    }
    return ""
}

// extractPublication pulls publication name from several potential locations.
func extractPublication(doc *goquery.Document, pageURL string) string {
    // Text inside explicit newsletter title link
    if v := strings.TrimSpace(doc.Find("h1.title-oOnUGd a").First().Text()); v != "" {
        return normalizePublication(v)
    }
    // Header h1 text (sometimes text node)
    if v := strings.TrimSpace(doc.Find("h1.title-oOnUGd").First().Text()); v != "" {
        return normalizePublication(v)
    }
    // Image alt attribute inside header (when logo only)
    if v, ok := doc.Find("h1.title-oOnUGd img[alt]").First().Attr("alt"); ok && strings.TrimSpace(v) != "" {
        return normalizePublication(v)
    }
    // OpenGraph site name
    if v := strings.TrimSpace(doc.Find("meta[property='og:site_name']").AttrOr("content", "")); v != "" {
        return normalizePublication(v)
    }
    // Twitter site or card site
    if v := strings.TrimSpace(doc.Find("meta[name='twitter:site']").AttrOr("content", "")); v != "" {
        return normalizePublication(strings.TrimPrefix(v, "@"))
    }
    // Fallback to host segment
    if u, e := url.Parse(pageURL); e == nil {
        host := u.Hostname()
        parts := strings.Split(host, ".")
        if len(parts) > 0 {
            return normalizePublication(strings.Title(parts[0]))
        }
    }
    return ""
}

func deriveFilename(rawURL string) string {
	// Extract path after last '/'
	parts := strings.Split(trailingSlash.ReplaceAllString(rawURL, ""), "/")
	last := parts[len(parts)-1]
	last = strings.Split(last, "?")[0]
	last = strings.Split(last, "#")[0]
	last = unsafeChars.ReplaceAllString(last, "-")
	last = strings.Trim(last, "-._")
	if last == "" {
		// Fallback to hash
		return fmt.Sprintf("article-%x.html", sha1.Sum([]byte(rawURL)))
	}
	if !strings.HasSuffix(strings.ToLower(last), ".html") {
		last += ".html"
	}
	return last
}
