package fetch

import (
	"bytes"
	"context"
	"crypto/sha1"
	"errors"
	"fmt"
	"io"
	"net/http"
	"os"
	"path/filepath"
	"regexp"
	"strings"
	"time"

	"github.com/PuerkitoBio/goquery"
	art "pdf-maker/internal/article"
	"pdf-maker/internal/clean"
	"pdf-maker/internal/media"
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
func FetchArticleWithImages(ctx context.Context, pageURL string, imageDownloader *media.Downloader) (*art.Article, []byte, error) {
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

    a := &art.Article{Link: pageURL}

    // Detect platform and dispatch to the appropriate content extractor
    platform := DetectPlatform(a.Platform, pageURL, doc)
    dispatchExtract(platform, doc, pageURL, a)

    // Ultimate fallback: if no extractor populated Content, use raw HTML
    if a.Content == "" {
        a.Content = string(raw)
    }

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
