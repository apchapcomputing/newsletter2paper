package main

import (
	"context"
	"flag"
	"fmt"
	"log"
	"strings"
	"time"

	art "newsletter2newspaper/internal/article"
	"newsletter2newspaper/internal/fetch"
)

// DefaultArticleURL is the initial target article if none provided via flag.
const DefaultArticleURL = "https://kyla.substack.com/p/chicago-fed-president-austan-goolsbee"

func main() {
	singleURL := flag.String("url", "", "Single article URL (ignored if -urls provided)")
	multiURLs := flag.String("urls", "", "Comma-separated list of article URLs to fetch concurrently")
	outDir := flag.String("out", "articles", "Output directory for saved HTML content files")
	timeout := flag.Duration("timeout", 30*time.Second, "Timeout for overall fetch operation")
	maxPar := flag.Int("max-par", 4, "Maximum parallel fetches when using -urls")
	flag.Parse()

	urls := []string{}
	if *multiURLs != "" {
		parts := strings.Split(*multiURLs, ",")
		for _, p := range parts {
			p = strings.TrimSpace(p)
			if p != "" { urls = append(urls, p) }
		}
	} else {
		if *singleURL == "" { *singleURL = DefaultArticleURL }
		urls = append(urls, *singleURL)
	}

	ctx, cancel := context.WithTimeout(context.Background(), *timeout)
	defer cancel()

	if len(urls) == 1 { // original single-path behavior
		article, _, err := fetch.FetchArticle(ctx, urls[0])
		if err != nil { log.Fatalf("fetch failed: %v", err) }
		path, err := fetch.FetchAndSaveArticle(ctx, urls[0], *outDir)
		if err != nil { log.Fatalf("save failed: %v", err) }
		printArticle(article, path)
		return
	}

	// Concurrent path
	fmt.Printf("Fetching %d articles (max parallel=%d) ...\n", len(urls), *maxPar)
	arts, errs := fetch.FetchArticlesConcurrent(ctx, urls, *maxPar)

	// Save each article content
	for _, a := range arts {
		path, err := fetch.FetchAndSaveArticle(ctx, a.Link, *outDir)
		if err != nil { fmt.Printf("ERROR saving %s: %v\n", a.Link, err); continue }
		printArticle(a, path)
		fmt.Println("------------------------------")
	}

	if len(errs) > 0 {
		fmt.Printf("%d fetches failed:\n", len(errs))
		for _, e := range errs { fmt.Printf("  - %v\n", e) }
	}
}

// printArticle outputs metadata for a fetched article.
func printArticle(a *art.Article, path string) {
	fmt.Printf("Saved article to: %s\n", path)
	fmt.Println("--- Extracted Metadata ---")
	fmt.Printf("Title: %s\n", a.Title)
	if a.Subtitle != "" { fmt.Printf("Subtitle: %s\n", a.Subtitle) }
	if a.Author != "" { fmt.Printf("Author: %s\n", a.Author) }
	if a.Publication != "" { fmt.Printf("Publication: %s\n", a.Publication) }
	if !a.PubDate.IsZero() { fmt.Printf("Published: %s\n", a.PubDate.Format(time.RFC3339)) }
	fmt.Printf("Link: %s\n", a.Link)
}
