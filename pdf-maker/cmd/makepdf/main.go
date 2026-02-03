package main

import (
	"context"
	"flag"
	"fmt"
	"log"
	"strings"
	"time"

	art "pdf-maker/internal/article"
	"pdf-maker/internal/fetch"
	"pdf-maker/internal/media"
	"pdf-maker/internal/pdf"
)

func main() {
	urls := flag.String("urls", "", "Comma-separated list of article URLs to fetch and convert to PDF")
	articlesJSON := flag.String("articles-json", "", "Path to JSON file containing article data (alternative to --urls)")
	output := flag.String("output", "", "Output PDF path (default: newspapers/articles_TIMESTAMP.pdf)")
	title := flag.String("title", "Your Articles", "PDF header title")
	layoutType := flag.String("layout-type", "newspaper", "PDF layout type: 'newspaper' or 'essay' (used with --urls, ignored with --articles-json)")
	keepHTML := flag.Bool("keep-html", false, "Keep intermediate HTML file for debugging")
	removeImages := flag.Bool("remove-images", false, "Remove all images from the PDF (text-only)")
	cleanupImages := flag.Bool("cleanup-images", true, "Delete downloaded images after PDF generation")
	maxPar := flag.Int("max-par", 4, "Maximum parallel fetches")
	timeout := flag.Duration("timeout", 90*time.Second, "Total operation timeout")
	flag.Parse()

	// Must provide either --urls or --articles-json
	if *urls == "" && *articlesJSON == "" {
		log.Fatal("Either --urls or --articles-json is required")
	}

	if *urls != "" && *articlesJSON != "" {
		log.Fatal("Cannot use both --urls and --articles-json; choose one")
	}

	ctx, cancel := context.WithTimeout(context.Background(), *timeout)
	defer cancel()

	// Create image downloader
	imgDownloader, err := media.NewDownloader("images")
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

	var articles []*art.Article
	var errs []error
	var layout string // The actual layout type to use

	// Process based on input method
	if *articlesJSON != "" {
		// Load articles from JSON file - layout type comes from JSON
		articles, errs, layout = processArticlesFromJSON(ctx, *articlesJSON, imgDownloader, *maxPar)
	} else {
		// Original URL-based processing - layout type comes from flag
		urlList := parseURLs(*urls)
		if len(urlList) == 0 {
			log.Fatal("no valid URLs provided")
		}

		// Validate layout type flag
		if *layoutType != "newspaper" && *layoutType != "essay" {
			log.Fatalf("Invalid layout type '%s'. Must be 'newspaper' or 'essay'", *layoutType)
		}

		fmt.Printf("Fetching %d articles (max parallel=%d)...\n", len(urlList), *maxPar)
		articles, errs = fetch.FetchArticlesConcurrentWithImages(ctx, urlList, *maxPar, imgDownloader)
		layout = *layoutType // Use the flag value
	}

	if len(errs) > 0 {
		fmt.Printf("⚠️  %d fetch errors:\n", len(errs))
		for _, e := range errs {
			fmt.Printf("  - %v\n", e)
		}
	}

	if len(articles) == 0 {
		log.Fatal("no articles successfully fetched; cannot generate PDF")
	}

	if len(errs) > 0 {
		fmt.Printf("✅ Successfully processed %d articles (with %d errors)\n", len(articles), len(errs))
	} else {
		fmt.Printf("✅ Successfully processed %d articles\n", len(articles))
	}

	// Generate PDF
	fmt.Println("Generating PDF...")
	opts := pdf.GenerateOptions{
		OutputPath:   *output,
		Title:        *title,
		KeepHTML:     *keepHTML,
		LayoutType:   layout,
		RemoveImages: *removeImages,
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

// parseURLs extracts URLs from comma-separated string
func parseURLs(urls string) []string {
	urlList := []string{}
	for _, u := range strings.Split(urls, ",") {
		u = strings.TrimSpace(u)
		if u != "" {
			urlList = append(urlList, u)
		}
	}
	return urlList
}

// processArticlesFromJSON loads articles from JSON and fetches content if needed
func processArticlesFromJSON(ctx context.Context, jsonPath string, imgDownloader *media.Downloader, maxPar int) ([]*art.Article, []error, string) {
	fmt.Printf("Loading articles from JSON: %s\n", jsonPath)

	issueInput, err := art.LoadArticlesFromJSON(jsonPath)
	if err != nil {
		log.Fatalf("Failed to load JSON: %v", err)
	}

	fmt.Printf("Loaded %d articles from issue: %s\n", len(issueInput.Articles), issueInput.IssueTitle)

	// Get layout type from JSON (default to "newspaper" if not specified)
	layoutType := issueInput.LayoutType
	if layoutType == "" {
		layoutType = "newspaper"
	}

	articles := make([]*art.Article, 0, len(issueInput.Articles))
	errs := make([]error, 0)

	// Track which articles need content fetching
	articlesToFetch := []string{}
	articleIndices := []int{}

	for i, input := range issueInput.Articles {
		article := input.ToArticle()

		// If content is provided directly, use it
		if input.Content != "" {
			articles = append(articles, article)
			fmt.Printf("  [%d/%d] Using provided content: %s\n", i+1, len(issueInput.Articles), article.Title)
		} else if input.ContentURL != "" {
			// Mark for fetching
			articlesToFetch = append(articlesToFetch, input.ContentURL)
			articleIndices = append(articleIndices, len(articles))
			articles = append(articles, article) // placeholder
			fmt.Printf("  [%d/%d] Will fetch: %s\n", i+1, len(issueInput.Articles), input.ContentURL)
		} else {
			// No content and no URL
			err := fmt.Errorf("article '%s' has neither content nor content_url", article.Title)
			errs = append(errs, err)
			fmt.Printf("  [%d/%d] ⚠️  Error: %v\n", i+1, len(issueInput.Articles), err)
		}
	}

	// Fetch articles that need fetching
	if len(articlesToFetch) > 0 {
		fmt.Printf("\nFetching %d articles (max parallel=%d)...\n", len(articlesToFetch), maxPar)
		fetchedArticles, fetchErrs := fetch.FetchArticlesConcurrentWithImages(ctx, articlesToFetch, maxPar, imgDownloader)

		// Map fetched articles back to their positions
		fetchedIndex := 0
		for i, idx := range articleIndices {
			if fetchedIndex < len(fetchedArticles) && fetchedArticles[fetchedIndex] != nil {
				// Merge fetched content with existing metadata
				original := articles[idx]
				fetched := fetchedArticles[fetchedIndex]

				// Keep original metadata if it was provided, use fetched as fallback
				if original.Title == "" {
					original.Title = fetched.Title
				}
				if original.Author == "" {
					original.Author = fetched.Author
				}
				if original.Publication == "" {
					original.Publication = fetched.Publication
				}
				original.Content = fetched.Content
				// RemoveImages is already preserved from original ArticleInput

				articles[idx] = original
				fetchedIndex++
			} else {
				// Fetch failed for this article
				if i < len(fetchErrs) {
					errs = append(errs, fetchErrs[i])
				}
			}
		}

		// Add any remaining fetch errors
		if len(fetchErrs) > len(articleIndices) {
			errs = append(errs, fetchErrs[len(articleIndices):]...)
		}
	}

	// Filter out articles with no content
	validArticles := make([]*art.Article, 0, len(articles))
	for _, a := range articles {
		if a.Content != "" {
			validArticles = append(validArticles, a)
		}
	}

	return validArticles, errs, layoutType
}
