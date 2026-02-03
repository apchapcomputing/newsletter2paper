package main

import (
	"context"
	"flag"
	"fmt"
	"log"
	"os"
	"path/filepath"
	"strings"
	"time"

	art "pdf-maker/internal/article"
	"pdf-maker/internal/clean"
	"pdf-maker/internal/fetch"
)

// DefaultArticleURL is the initial target article if none provided via flag.
const DefaultArticleURL = "https://kyla.substack.com/p/chicago-fed-president-austan-goolsbee"

func main() {
	singleURL := flag.String("url", "", "Single article URL (ignored if -urls provided)")
	multiURLs := flag.String("urls", "", "Comma-separated list of article URLs to fetch concurrently")
	outDir := flag.String("out", "articles", "Output directory for saved HTML content files")
	timeout := flag.Duration("timeout", 30*time.Second, "Timeout for overall fetch operation")
	maxPar := flag.Int("max-par", 4, "Maximum parallel fetches when using -urls")
	removeImages := flag.Bool("remove-images", false, "Remove all image elements from the article HTML")
	flag.Parse()

	urls := []string{}
	if *multiURLs != "" {
		parts := strings.Split(*multiURLs, ",")
		for _, p := range parts {
			p = strings.TrimSpace(p)
			if p != "" {
				urls = append(urls, p)
			}
		}
	} else {
		if *singleURL == "" {
			*singleURL = DefaultArticleURL
		}
		urls = append(urls, *singleURL)
	}

	ctx, cancel := context.WithTimeout(context.Background(), *timeout)
	defer cancel()

	if len(urls) == 1 { // original single-path behavior
		article, _, err := fetch.FetchArticle(ctx, urls[0])
		if err != nil {
			log.Fatalf("fetch failed: %v", err)
		}

		// Apply image removal if flag is set
		if *removeImages {
			article = removeImagesFromArticle(article)
		}

		path, err := saveArticleContent(article, urls[0], *outDir)
		if err != nil {
			log.Fatalf("save failed: %v", err)
		}
		printArticle(article, path)
		return
	}

	// Concurrent path
	fmt.Printf("Fetching %d articles (max parallel=%d) ...\n", len(urls), *maxPar)
	arts, errs := fetch.FetchArticlesConcurrent(ctx, urls, *maxPar)

	// Save each article content
	for _, a := range arts {
		// Apply image removal if flag is set
		if *removeImages {
			a = removeImagesFromArticle(a)
		}

		path, err := saveArticleContent(a, a.Link, *outDir)
		if err != nil {
			fmt.Printf("ERROR saving %s: %v\n", a.Link, err)
			continue
		}
		printArticle(a, path)
		fmt.Println("------------------------------")
	}

	if len(errs) > 0 {
		fmt.Printf("%d fetches failed:\n", len(errs))
		for _, e := range errs {
			fmt.Printf("  - %v\n", e)
		}
	}
}

// printArticle outputs metadata for a fetched article.
func printArticle(a *art.Article, path string) {
	fmt.Printf("Saved article to: %s\n", path)
	fmt.Println("--- Extracted Metadata ---")
	fmt.Printf("Title: %s\n", a.Title)
	if a.Subtitle != "" {
		fmt.Printf("Subtitle: %s\n", a.Subtitle)
	}
	if a.Author != "" {
		fmt.Printf("Author: %s\n", a.Author)
	}
	if a.Publication != "" {
		fmt.Printf("Publication: %s\n", a.Publication)
	}
	if !a.PubDate.IsZero() {
		fmt.Printf("Published: %s\n", a.PubDate.Format(time.RFC3339))
	}
	fmt.Printf("Link: %s\n", a.Link)
}

// removeImagesFromArticle removes all image elements from an article's content.
func removeImagesFromArticle(article *art.Article) *art.Article {
	cleaned, count, err := clean.RemoveAllImages(article.Content)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Warning: failed to remove images: %v\n", err)
		return article
	}

	if count > 0 {
		fmt.Printf("Removed %d image(s) from article\n", count)
	}

	article.Content = cleaned
	return article
}

// saveArticleContent saves an article's content to disk and returns the file path.
func saveArticleContent(article *art.Article, pageURL, outDir string) (string, error) {
	if outDir == "" {
		outDir = "."
	}

	filename := deriveFilename(pageURL)
	if err := os.MkdirAll(outDir, 0o755); err != nil {
		return "", fmt.Errorf("mkdir %s: %w", outDir, err)
	}

	absDir, err := filepath.Abs(outDir)
	if err != nil {
		return "", fmt.Errorf("abs dir: %w", err)
	}

	outPath := filepath.Join(absDir, filename)
	if err := os.WriteFile(outPath, []byte(article.Content), 0o644); err != nil {
		return "", fmt.Errorf("write file: %w", err)
	}

	return outPath, nil
}

// deriveFilename creates a safe filename from a URL.
func deriveFilename(pageURL string) string {
	// Simple filename derivation - extract last path segment
	parts := strings.Split(strings.TrimSuffix(pageURL, "/"), "/")
	if len(parts) > 0 {
		name := parts[len(parts)-1]
		// Sanitize the filename
		name = strings.ReplaceAll(name, " ", "_")
		name = strings.Map(func(r rune) rune {
			if (r >= 'a' && r <= 'z') || (r >= 'A' && r <= 'Z') || (r >= '0' && r <= '9') || r == '_' || r == '-' || r == '.' {
				return r
			}
			return '_'
		}, name)
		if name != "" {
			return name + ".html"
		}
	}
	return "article.html"
}
