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
	ImagesRemoved       int
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

	// Remove image control icons (expand, refresh buttons) and media controls
	imageControlSelectors := []string{
		".lucide-maximize2",
		".lucide-refresh-cw",
		".lucide-play",
		".lucide-pause",
		".lucide-volume",
		".lucide-speaker",
		"[class*='play-icon']",
		"[class*='pause-icon']",
		"[class*='media-icon']",
		"[data-testid*='play']",
		"[data-testid*='pause']",
		"[data-testid*='audio']",
		"[data-testid*='video']",
		".fa-play", // FontAwesome icons
		".fa-pause",
		".fa-volume-up",
		".fa-volume-down",
		".image-link-expand", // Substack image expansion buttons
		".restack-image",     // Restack image button
		".view-image",        // View image button
		".icon-container",    // Generic icon containers in image controls
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
		"[role='application']", // Many media players use this role
		".media-controls",
		".player-controls",
		"[class*='play-button']",
		"[class*='pause-button']",
		"[class*='media-control']",
	}
	for _, selector := range mediaPlayerSelectors {
		doc.Find(selector).Each(func(i int, s *goquery.Selection) {
			s.Remove()
			stats.ImageIcons++
		})
	}

	// Remove buttons and elements containing media control symbols (play, pause, etc.)
	doc.Find("button, div, span").Each(func(i int, s *goquery.Selection) {
		text := s.Text()
		// Check for common media control symbols
		if strings.Contains(text, "⏸") || // pause symbol
			strings.Contains(text, "▶") || // play symbol
			strings.Contains(text, "⏯") || // play/pause symbol
			strings.Contains(text, "⏭") || // next track
			strings.Contains(text, "⏮") || // previous track
			strings.Contains(text, "⏹") || // stop symbol
			strings.Contains(text, "🔊") || // volume symbol
			strings.Contains(text, "🔇") { // mute symbol
			s.Remove()
			stats.ImageIcons++
		}

		// Also check aria-label attributes for media controls
		if ariaLabel, exists := s.Attr("aria-label"); exists {
			lowerLabel := strings.ToLower(ariaLabel)
			if strings.Contains(lowerLabel, "play") ||
				strings.Contains(lowerLabel, "pause") ||
				strings.Contains(lowerLabel, "audio") ||
				strings.Contains(lowerLabel, "video") ||
				strings.Contains(lowerLabel, "media") {
				s.Remove()
				stats.ImageIcons++
			}
		}
	})

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

	// Post-process: normalize whitespace and remove excessive line breaks
	// This fixes issues where removed inline elements leave behind newlines
	cleaned = normalizeWhitespace(cleaned)

	return cleaned, stats, nil
}

// normalizeWhitespace cleans up excessive whitespace and newlines in HTML
// while preserving intentional spacing and structure
func normalizeWhitespace(html string) string {
	// Replace multiple consecutive newlines with single newline
	html = strings.ReplaceAll(html, "\n\n\n", "\n\n")
	html = strings.ReplaceAll(html, "\r\n\r\n\r\n", "\r\n\r\n")

	// Remove newlines that appear within inline text contexts
	// This regex finds newlines between text that aren't at tag boundaries
	html = strings.ReplaceAll(html, " \n ", " ")
	html = strings.ReplaceAll(html, " \n", " ")
	html = strings.ReplaceAll(html, "\n ", " ")

	// Clean up spaces around tags
	html = strings.ReplaceAll(html, "> <", "><")
	html = strings.ReplaceAll(html, ">\n<", "><")
	html = strings.ReplaceAll(html, ">\n\n<", "><")

	// Remove trailing/leading whitespace from paragraphs
	html = strings.ReplaceAll(html, "<p> ", "<p>")
	html = strings.ReplaceAll(html, " </p>", "</p>")
	html = strings.ReplaceAll(html, "<p>\n", "<p>")
	html = strings.ReplaceAll(html, "\n</p>", "</p>")

	return html
}

// RemoveAllImages removes all <img> tags and related elements from HTML content.
// This is useful for generating text-only PDFs without images.
// Returns cleaned HTML string and count of images removed.
func RemoveAllImages(htmlContent string) (string, int, error) {
	doc, err := goquery.NewDocumentFromReader(strings.NewReader(htmlContent))
	if err != nil {
		return "", 0, err
	}

	imagesRemoved := 0

	// Remove all <img> tags
	doc.Find("img").Each(func(i int, s *goquery.Selection) {
		s.Remove()
		imagesRemoved++
	})

	// Remove figure elements (which typically contain images)
	doc.Find("figure").Each(func(i int, s *goquery.Selection) {
		s.Remove()
	})

	// Remove picture elements (responsive image containers)
	doc.Find("picture").Each(func(i int, s *goquery.Selection) {
		s.Remove()
	})

	// Remove divs with image-related classes
	imageClassSelectors := []string{
		".captioned-image-container",
		".captioned-image",
		".image-container",
		".post-image",
		"[class*='image-']",
		"[class*='Image']",
	}
	for _, selector := range imageClassSelectors {
		doc.Find(selector).Each(func(i int, s *goquery.Selection) {
			s.Remove()
		})
	}

	// Get cleaned HTML
	cleaned, err := doc.Find("body").Html()
	if err != nil {
		return "", imagesRemoved, err
	}

	// If original content was a fragment (no body tag), extract just the body content
	if !strings.Contains(htmlContent, "<body") {
		cleaned = strings.TrimSpace(cleaned)
	}

	return cleaned, imagesRemoved, nil
}

// ExtractBlocks extracts top-level block elements from HTML content as individual
// self-contained HTML strings. This is used for newspaper column rendering to
// avoid unclosed wrapper divs (e.g. Substack's "<div dir=auto class=body markup>")
// that nest newspaper-page divs inside each other and break page-break-before.
func ExtractBlocks(htmlContent string) []string {
	doc, err := goquery.NewDocumentFromReader(strings.NewReader(htmlContent))
	if err != nil {
		return paragraphFallback(htmlContent)
	}

	body := doc.Find("body")
	source := body

	// Unwrap a single outer wrapper div (common in Substack content).
	// Substack wraps all article content in <div dir="auto" class="body markup">.
	children := body.Children()
	if children.Length() == 1 && goquery.NodeName(children.First()) == "div" {
		source = children.First()
	}

	var blocks []string
	source.Children().Each(func(_ int, s *goquery.Selection) {
		h, err := goquery.OuterHtml(s)
		if err != nil {
			return
		}
		if h = strings.TrimSpace(h); h != "" {
			blocks = append(blocks, h)
		}
	})

	if len(blocks) == 0 {
		return paragraphFallback(htmlContent)
	}
	return blocks
}

// paragraphFallback is a best-effort fallback that splits HTML at </p> boundaries.
func paragraphFallback(content string) []string {
	var blocks []string
	for _, p := range strings.Split(content, "</p>") {
		p = strings.TrimSpace(p)
		if p != "" {
			blocks = append(blocks, p+"</p>")
		}
	}
	return blocks
}
