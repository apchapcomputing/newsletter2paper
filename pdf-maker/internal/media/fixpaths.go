package media

import (
	"fmt"
	"path/filepath"
	"strings"

	"github.com/PuerkitoBio/goquery"
)

// FixImagePathsToAbsolute converts relative image paths to absolute file:// URLs.
// This is necessary for wkhtmltopdf to find images when the HTML file is in a different directory.
func FixImagePathsToAbsolute(htmlContent string, imagesDir string) (string, error) {
	doc, err := goquery.NewDocumentFromReader(strings.NewReader(htmlContent))
	if err != nil {
		return "", fmt.Errorf("parse html: %w", err)
	}

	// Get absolute path to images directory
	absImagesDir, err := filepath.Abs(imagesDir)
	if err != nil {
		return "", fmt.Errorf("get absolute path: %w", err)
	}

	// Find all images and update their paths
	doc.Find("img").Each(func(i int, img *goquery.Selection) {
		src, exists := img.Attr("src")
		if !exists || src == "" {
			return
		}

		// Only process relative paths to images directory
		if strings.HasPrefix(src, imagesDir+"/") || strings.HasPrefix(src, "./"+imagesDir+"/") {
			// Extract filename
			filename := filepath.Base(src)
			// Create absolute file:// URL
			absolutePath := filepath.Join(absImagesDir, filename)
			fileURL := fmt.Sprintf("file://%s", absolutePath)
			img.SetAttr("src", fileURL)
		}
	})

	// Get modified HTML
	html, err := doc.Find("body").Html()
	if err != nil {
		return "", fmt.Errorf("extract html: %w", err)
	}

	// If original was a full document, get the whole thing
	if strings.Contains(htmlContent, "<html") {
		html, err = goquery.OuterHtml(doc.Selection)
		if err != nil {
			return "", fmt.Errorf("extract full html: %w", err)
		}
	}

	return html, nil
}
