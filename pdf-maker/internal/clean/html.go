package clean

import (
	"strings"

	"github.com/PuerkitoBio/goquery"
)

// Stats tracks the number of elements removed/modified during cleaning.
type Stats struct {
	SubscriptionWidgets int
	Forms               int
	Inputs              int
	SubscriptionElems   int
	ImageIcons          int
	FootnotesFormatted  int
}

// CleanHTML removes subscription widgets, forms, and formats footnotes for better PDF rendering.
// Returns cleaned HTML string and statistics about what was removed.
func CleanHTML(htmlContent string, verbose bool) (string, Stats, error) {
	stats := Stats{}

	doc, err := goquery.NewDocumentFromReader(strings.NewReader(htmlContent))
	if err != nil {
		return "", stats, err
	}

	// Remove subscription widgets
	doc.Find("div.subscription-widget-wrap-editor").Each(func(i int, s *goquery.Selection) {
		s.Remove()
		stats.SubscriptionWidgets++
	})

	// Remove all forms (subscription forms, etc.)
	doc.Find("form").Each(func(i int, s *goquery.Selection) {
		s.Remove()
		stats.Forms++
	})

	// Remove all input elements
	doc.Find("input").Each(func(i int, s *goquery.Selection) {
		s.Remove()
		stats.Inputs++
	})

	// Remove elements with subscription-related classes
	subscriptionSelectors := []string{
		"[class*='subscription']",
		"[class*='subscribe']",
		"[class*='email-input']",
		"[data-component-name*='Subscribe']",
	}
	for _, selector := range subscriptionSelectors {
		doc.Find(selector).Each(func(i int, s *goquery.Selection) {
			s.Remove()
			stats.SubscriptionElems++
		})
	}

	// Remove image control icons (expand, refresh buttons)
	imageControlSelectors := []string{
		".lucide-maximize2",
		".lucide-refresh-cw",
	}
	for _, selector := range imageControlSelectors {
		doc.Find(selector).Each(func(i int, s *goquery.Selection) {
			s.Remove()
			stats.ImageIcons++
		})
	}

	// Remove link/share buttons (chain link icons)
	linkButtonSelectors := []string{
		"a[aria-label*='chain']",
		"a[aria-label*='link']",
		"button[aria-label*='chain']",
		"button[aria-label='Link']", // Exact match for link buttons
		"button[aria-label*='link']",
		".pencraft.pc-reset._color-secondary_1iure_186[href='#']",
		"svg[aria-label*='chain']",
	}
	for _, selector := range linkButtonSelectors {
		doc.Find(selector).Each(func(i int, s *goquery.Selection) {
			s.Remove()
			stats.ImageIcons++
		})
	}
	
	// Remove buttons containing lucide-link SVG icons
	doc.Find("button").Each(func(i int, s *goquery.Selection) {
		if s.Find("svg.lucide-link").Length() > 0 {
			s.Remove()
			stats.ImageIcons++
		}
	})

	// Remove injected scripts (like live-server, analytics, etc.)
	doc.Find("script").Each(func(i int, s *goquery.Selection) {
		scriptContent, _ := s.Html()
		// Remove live-server and similar development scripts
		if strings.Contains(scriptContent, "live-server") ||
			strings.Contains(scriptContent, "LiveServer") ||
			strings.Contains(scriptContent, "live reload") {
			s.Remove()
		}
	})

	// Remove email input fields and subscribe buttons more aggressively
	doc.Find("input[type='email']").Each(func(i int, s *goquery.Selection) {
		s.Remove()
		stats.Inputs++
	})
	doc.Find("button").Each(func(i int, s *goquery.Selection) {
		text := strings.ToLower(s.Text())
		if strings.Contains(text, "subscribe") || strings.Contains(text, "sign up") {
			s.Remove()
			stats.SubscriptionElems++
		}
	})

	// Remove media players (audio/video elements and their containers)
	doc.Find("audio").Each(func(i int, s *goquery.Selection) {
		s.Remove()
		stats.ImageIcons++
	})
	doc.Find("video").Each(func(i int, s *goquery.Selection) {
		s.Remove()
		stats.ImageIcons++
	})
	// Remove media player containers by class patterns
	mediaPlayerSelectors := []string{
		"[class*='audio-player']",
		"[class*='video-player']",
		"[class*='media-player']",
		"[class*='plyr']", // common player library
		".audio-module",
		".video-module",
		"[data-component-name='AudioEmbedPlayer']", // Substack audio players
		"[data-component-name='VideoEmbedPlayer']", // Substack video players
		"[aria-label='Audio embed player']",
		"[aria-label='Video embed player']",
	}
	for _, selector := range mediaPlayerSelectors {
		doc.Find(selector).Each(func(i int, s *goquery.Selection) {
			s.Remove()
			stats.ImageIcons++
		})
	}

	// Format footnotes: convert multi-line footnotes to inline format
	doc.Find("div.footnote").Each(func(i int, footnote *goquery.Selection) {
		footnoteNum := footnote.Find("a.footnote-number").First()
		footnoteContent := footnote.Find("div.footnote-content").First()

		if footnoteNum.Length() > 0 && footnoteContent.Length() > 0 {
			numberText := strings.TrimSpace(footnoteNum.Text())
			contentP := footnoteContent.Find("p").First()

			if contentP.Length() > 0 {
				// Create new inline paragraph
				newP := doc.Find("body").AppendHtml("<p></p>").Find("p").Last()
				newP.SetAttr("style", "margin-bottom: 6px; text-indent: -1em; padding-left: 1em;")

				// Create footnote number anchor
				href, _ := footnoteNum.Attr("href")
				id, _ := footnoteNum.Attr("id")
				target, exists := footnoteNum.Attr("target")
				if !exists {
					target = "_self"
				}

				newA := doc.Find("body").AppendHtml("<a></a>").Find("a").Last()
				newA.SetAttr("href", href)
				newA.SetAttr("id", id)
				newA.SetAttr("target", target)
				newA.SetAttr("style", "font-weight: bold; text-decoration: none;")
				newA.SetText(numberText + ". ")

				// Get inner HTML of content paragraph
				contentHTML, _ := contentP.Html()

				// Move the anchor and content into the new paragraph
				newP.Empty()
				newP.AppendSelection(newA)
				newP.AppendHtml(contentHTML)

				// Replace original footnote with new format
				footnote.ReplaceWithSelection(newP)
				stats.FootnotesFormatted++
			}
		}
	})

	// Get cleaned HTML
	cleaned, err := doc.Find("body").Html()
	if err != nil {
		return "", stats, err
	}

	// If original content was a fragment (no body tag), extract just the body content
	if !strings.Contains(htmlContent, "<body") {
		cleaned = strings.TrimSpace(cleaned)
	}

	return cleaned, stats, nil
}
