package media

import (
	"crypto/md5"
	"fmt"
	"io"
	"net/http"
	"net/url"
	"os"
	"path/filepath"
	"strings"
	"time"

	"github.com/PuerkitoBio/goquery"
)

// Downloader manages image downloading with configurable options.
type Downloader struct {
	opts      DownloadOptions
	imagesDir string
}

// NewDownloader creates a new image downloader with the given directory.
// This is a convenience constructor that sets up default options.
func NewDownloader(imagesDir string) (*Downloader, error) {
	if imagesDir == "" {
		imagesDir = "images"
	}
	
	// Create images directory
	if err := os.MkdirAll(imagesDir, 0o755); err != nil {
		return nil, fmt.Errorf("create images dir: %w", err)
	}
	
	return &Downloader{
		imagesDir: imagesDir,
		opts: DownloadOptions{
			ImagesDir: imagesDir,
			Timeout:   10 * time.Second,
			UserAgent: "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
			Verbose:   false,
		},
	}, nil
}

// NewDownloaderWithOptions creates a new image downloader with custom options.
func NewDownloaderWithOptions(opts DownloadOptions) (*Downloader, error) {
	// Set defaults
	if opts.ImagesDir == "" {
		opts.ImagesDir = "images"
	}
	if opts.Timeout == 0 {
		opts.Timeout = 10 * time.Second
	}
	if opts.UserAgent == "" {
		opts.UserAgent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
	}
	
	// Create images directory
	if err := os.MkdirAll(opts.ImagesDir, 0o755); err != nil {
		return nil, fmt.Errorf("create images dir: %w", err)
	}
	
	return &Downloader{
		imagesDir: opts.ImagesDir,
		opts:      opts,
	}, nil
}

// SetVerbose enables or disables verbose output.
func (d *Downloader) SetVerbose(verbose bool) {
	d.opts.Verbose = verbose
}

// ProcessHTML is a convenience method that downloads images from HTML content.
func (d *Downloader) ProcessHTML(htmlContent string) (string, error) {
	modifiedHTML, _, err := DownloadAndCacheImages(htmlContent, d.opts)
	return modifiedHTML, err
}

// Cleanup removes all downloaded images in the images directory.
func (d *Downloader) Cleanup() error {
	return os.RemoveAll(d.imagesDir)
}

// DownloadStats tracks the results of image downloading.
type DownloadStats struct {
	TotalImages      int
	Downloaded       int
	Cached           int
	Failed           int
	FailedURLs       []string // URLs that failed to download
}

// DownloadOptions configures image downloading behavior.
type DownloadOptions struct {
	ImagesDir  string        // Directory to save images (default: "images")
	Timeout    time.Duration // HTTP timeout per image (default: 10s)
	UserAgent  string        // Custom User-Agent header
	Verbose    bool          // Enable verbose logging
}

// DownloadAndCacheImages downloads images from HTML content and replaces URLs with local file paths.
// This function:
// 1. Parses the HTML to find all <img> tags
// 2. Downloads images that aren't already cached
// 3. Replaces src attributes with local file paths
// 4. Returns modified HTML with local image references
func DownloadAndCacheImages(htmlContent string, opts DownloadOptions) (string, DownloadStats, error) {
	stats := DownloadStats{}

	// Set defaults
	if opts.ImagesDir == "" {
		opts.ImagesDir = "images"
	}
	if opts.Timeout == 0 {
		opts.Timeout = 10 * time.Second
	}
	if opts.UserAgent == "" {
		opts.UserAgent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
	}

	// Parse HTML
	doc, err := goquery.NewDocumentFromReader(strings.NewReader(htmlContent))
	if err != nil {
		return "", stats, fmt.Errorf("parse html: %w", err)
	}

	// Find all images
	images := doc.Find("img")
	stats.TotalImages = images.Length()

	if stats.TotalImages == 0 {
		if opts.Verbose {
			fmt.Println("  - No images found in content")
		}
		html, _ := doc.Find("body").Html()
		return html, stats, nil
	}

	if opts.Verbose {
		fmt.Println("Processing images for local caching...")
	}

	// Create images directory
	if err := os.MkdirAll(opts.ImagesDir, 0o755); err != nil {
		return "", stats, fmt.Errorf("create images dir: %w", err)
	}

	// Create HTTP client with timeout
	client := &http.Client{
		Timeout: opts.Timeout,
	}

	// Process each image
	images.Each(func(i int, img *goquery.Selection) {
		src, exists := img.Attr("src")
		if !exists || src == "" {
			return
		}

		// Generate unique filename based on URL hash
		urlHash := fmt.Sprintf("%x", md5.Sum([]byte(src)))

		// Get file extension from URL
		ext := getImageExtension(src)
		filename := fmt.Sprintf("%s.%s", urlHash, ext)
		localPath := filepath.Join(opts.ImagesDir, filename)

		// Check if image already exists (cached)
		if _, err := os.Stat(localPath); err == nil {
			if opts.Verbose {
				fmt.Printf("  - Using cached image: %s\n", filename)
			}
			img.SetAttr("src", localPath)
			// Remove srcset to prevent browser/wkhtmltopdf from using remote URLs
			img.RemoveAttr("srcset")
			// Also remove srcset from parent picture/source elements
			img.Parent().Find("source").RemoveAttr("srcset")
			stats.Cached++
			return
		}

		// Download the image
		if opts.Verbose {
			truncatedSrc := src
			if len(src) > 60 {
				truncatedSrc = src[:60] + "..."
			}
			fmt.Printf("  - Downloading: %s\n", truncatedSrc)
		}

		if err := downloadImage(client, src, localPath, opts.UserAgent); err != nil {
			stats.Failed++
			stats.FailedURLs = append(stats.FailedURLs, src)
			if opts.Verbose {
				errMsg := err.Error()
				if len(errMsg) > 60 {
					errMsg = errMsg[:60] + "..."
				}
				fmt.Printf("    ❌ Failed to download image: %s\n", errMsg)
			}
			// Remove the img tag on failure
			img.Remove()
			return
		}

		// Update img src to local path
		img.SetAttr("src", localPath)
		// Remove srcset to prevent browser/wkhtmltopdf from using remote URLs
		img.RemoveAttr("srcset")
		// Also remove srcset from parent picture/source elements
		img.Parent().Find("source").RemoveAttr("srcset")
		stats.Downloaded++

		if opts.Verbose {
			fmt.Printf("    ✅ Saved as: %s\n", filename)
		}
	})

	if opts.Verbose {
		fmt.Printf("  - Downloaded: %d images\n", stats.Downloaded)
		fmt.Printf("  - Cached: %d images\n", stats.Cached)
		fmt.Printf("  - Failed: %d images\n", stats.Failed)
		fmt.Printf("  - Total processed: %d images\n", stats.TotalImages)
	}

	// Get modified HTML
	html, err := doc.Find("body").Html()
	if err != nil {
		return "", stats, fmt.Errorf("extract html: %w", err)
	}

	// If original content was a fragment (no body tag), extract just the body content
	if !strings.Contains(htmlContent, "<body") {
		html = strings.TrimSpace(html)
	}

	return html, stats, nil
}

// downloadImage downloads an image from a URL and saves it to a local file.
func downloadImage(client *http.Client, imageURL, localPath, userAgent string) error {
	// Create HTTP request
	req, err := http.NewRequest("GET", imageURL, nil)
	if err != nil {
		return fmt.Errorf("create request: %w", err)
	}

	// Set User-Agent header to avoid bot detection
	req.Header.Set("User-Agent", userAgent)

	// Execute request
	resp, err := client.Do(req)
	if err != nil {
		return fmt.Errorf("http get: %w", err)
	}
	defer resp.Body.Close()

	// Check status code
	if resp.StatusCode != http.StatusOK {
		return fmt.Errorf("http status %d", resp.StatusCode)
	}

	// Create output file
	outFile, err := os.Create(localPath)
	if err != nil {
		return fmt.Errorf("create file: %w", err)
	}
	defer outFile.Close()

	// Stream image data to file in chunks
	_, err = io.Copy(outFile, resp.Body)
	if err != nil {
		// Clean up partial file on error
		os.Remove(localPath)
		return fmt.Errorf("write file: %w", err)
	}

	return nil
}

// getImageExtension extracts the file extension from an image URL.
// Returns a valid image extension or defaults to "jpg".
func getImageExtension(imageURL string) string {
	// Parse URL
	parsedURL, err := url.Parse(imageURL)
	if err != nil {
		return "jpg" // Default fallback
	}

	// Get path and split by dots
	path := parsedURL.Path
	parts := strings.Split(path, ".")

	if len(parts) > 1 {
		ext := strings.ToLower(parts[len(parts)-1])

		// Validate common image extensions
		validExts := map[string]bool{
			"jpg":  true,
			"jpeg": true,
			"png":  true,
			"gif":  true,
			"webp": true,
			"svg":  true,
		}

		if validExts[ext] {
			return ext
		}
	}

	// Default fallback
	return "jpg"
}
