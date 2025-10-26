package main

import (
	"context"
	"flag"
	"fmt"
	"log"
	"strings"
	"time"

	"newsletter2newspaper/internal/fetch"
	"newsletter2newspaper/internal/images"
	"newsletter2newspaper/internal/pdf"
)

func main() {
	urls := flag.String("urls", "", "Comma-separated list of article URLs to fetch and convert to PDF")
	output := flag.String("output", "", "Output PDF path (default: newspapers/articles_TIMESTAMP.pdf)")
	title := flag.String("title", "Your Articles", "PDF header title")
	keepHTML := flag.Bool("keep-html", false, "Keep intermediate HTML file for debugging")
	cleanupImages := flag.Bool("cleanup-images", true, "Delete downloaded images after PDF generation")
	maxPar := flag.Int("max-par", 4, "Maximum parallel fetches")
	timeout := flag.Duration("timeout", 90*time.Second, "Total operation timeout")
	flag.Parse()

	if *urls == "" {
		log.Fatal("--urls is required (comma-separated list of article URLs)")
	}

	// Parse URLs
	urlList := []string{}
	for _, u := range strings.Split(*urls, ",") {
		u = strings.TrimSpace(u)
		if u != "" {
			urlList = append(urlList, u)
		}
	}

	if len(urlList) == 0 {
		log.Fatal("no valid URLs provided")
	}

	ctx, cancel := context.WithTimeout(context.Background(), *timeout)
	defer cancel()

	// Create image downloader
	imgDownloader, err := images.NewDownloader("images")
	if err != nil {
		log.Fatalf("Failed to create image downloader: %v", err)
	}
	
	// Cleanup images after PDF generation if requested
	if *cleanupImages {
		defer func() {
			fmt.Println("Cleaning up downloaded images...")
			if err := imgDownloader.Cleanup(); err != nil {
				fmt.Printf("Warning: cleanup failed: %v\n", err)
			}
		}()
	}

	// Fetch articles concurrently
	fmt.Printf("Fetching %d articles (max parallel=%d)...\n", len(urlList), *maxPar)
	articles, errs := fetch.FetchArticlesConcurrentWithImages(ctx, urlList, *maxPar, imgDownloader)

	if len(errs) > 0 {
		fmt.Printf("⚠️  %d fetch errors:\n", len(errs))
		for _, e := range errs {
			fmt.Printf("  - %v\n", e)
		}
	}

	if len(articles) == 0 {
		log.Fatal("no articles successfully fetched; cannot generate PDF")
	}

	fmt.Printf("✅ Successfully fetched %d/%d articles\n", len(articles), len(urlList))

	// Generate PDF
	fmt.Println("Generating PDF...")
	opts := pdf.GenerateOptions{
		OutputPath: *output,
		Title:      *title,
		KeepHTML:   *keepHTML,
	}

	result := pdf.GeneratePDF(ctx, articles, opts)
	if !result.Success {
		log.Fatalf("PDF generation failed: %v", result.Error)
	}

	fmt.Printf("✅ PDF generated: %s\n", result.PDFPath)
	if result.HTMLPath != "" {
		fmt.Printf("📄 HTML saved: %s\n", result.HTMLPath)
	}

	fmt.Println("\n--- Articles Included ---")
	for i, a := range articles {
		fmt.Printf("%d. %s", i+1, a.Title)
		if a.Author != "" {
			fmt.Printf(" (by %s)", a.Author)
		}
		fmt.Println()
	}
}
