package pdf

import (
	"bytes"
	"embed"
	"fmt"
	"html"
	"html/template"
	"path/filepath"
	"regexp"
	"strings"
	"time"

	art "pdf-maker/internal/article"
	"pdf-maker/internal/clean"
)

//go:embed templates/newspaper.gohtml templates/essay.gohtml
var layoutTemplates embed.FS

// Package-level parsed templates — parsed once at program start.
var (
	newspaperTmpl = template.Must(template.ParseFS(layoutTemplates, "templates/newspaper.gohtml"))
	essayTmpl     = template.Must(template.ParseFS(layoutTemplates, "templates/essay.gohtml"))
)

// npColumn holds pre-rendered HTML parts for one table column.
type npColumn struct {
	Parts []template.HTML
}

// npPage represents one physical page in the newspaper layout.
type npPage struct {
	Class   string
	Columns []npColumn
}

// npData is the data struct passed to templates/newspaper.gohtml.
type npData struct {
	CSSPath  template.URL
	Title    string
	Subtitle string
	Pages    []npPage
}

// essayTOCEntry is one line item in the essay Table of Contents.
type essayTOCEntry struct {
	Num         int
	Title       string
	Author      string
	Publication string
}

// essayData is the data struct passed to templates/essay.gohtml.
type essayData struct {
	CSSPath  template.URL
	Title    string
	Subtitle string
	TOC      []essayTOCEntry
	Articles []template.HTML
}

// AssembleHTML builds the complete HTML document for the given layout.
// layoutType can be "essay" or "newspaper" (default).
// HTML structure is driven by templates/newspaper.gohtml or templates/essay.gohtml.
func AssembleHTML(articles []*art.Article, title string, layoutType ...string) (string, error) {
	layout := "newspaper"
	if len(layoutType) > 0 && layoutType[0] != "" {
		if layoutType[0] == "essay" || layoutType[0] == "newspaper" {
			layout = layoutType[0]
		}
	}

	cssAbsPath, _ := filepath.Abs(fmt.Sprintf("styles/%s.css", layout))
	cssURL := template.URL("file://" + cssAbsPath)

	articleCount := len(articles)
	articleWord := "Articles"
	if articleCount == 1 {
		articleWord = "Article"
	}
	subtitle := fmt.Sprintf("%s \u2022 %d %s",
		time.Now().Format("Monday, January 2, 2006"), articleCount, articleWord)

	var buf bytes.Buffer
	if layout == "newspaper" {
		data := buildNewspaperData(articles, cssURL, title, subtitle)
		if err := newspaperTmpl.Execute(&buf, data); err != nil {
			return "", fmt.Errorf("newspaper template: %w", err)
		}
	} else {
		data := buildEssayData(articles, cssURL, title, subtitle)
		if err := essayTmpl.Execute(&buf, data); err != nil {
			return "", fmt.Errorf("essay template: %w", err)
		}
	}
	return buf.String(), nil
}

// ---------------------------------------------------------------------------
// Newspaper layout helpers
// ---------------------------------------------------------------------------

var (
	htmlTagRe   = regexp.MustCompile(`<[^>]+>`)
	imgTagRe    = regexp.MustCompile(`(?i)<img\b[^>]*/?>`)
	imgWidthRe  = regexp.MustCompile(`(?i)<img[^>]*\swidth=["']?(\d+)`)
	imgHeightRe = regexp.MustCompile(`(?i)<img[^>]*\sheight=["']?(\d+)`)
)

// npEstChars estimates the visual character footprint of an HTML snippet.
// Images are estimated by their actual rendered height in the column:
//   - Column width: ~3.3in (10in page - 1in margins / 3 cols - 0.67in padding)
//   - Images render at width:100%, max-height:2.5in
//   - If image has width/height attrs, calculate aspect-ratio rendered height
//   - Otherwise assume 2.5in (worst case)
//
// At 10pt/1.4 line-height (0.194in/line) × 48 chars/line:
//
//	1in ≈ 247 chars, so heights vary: 1.85in (16:9) ≈ 457 chars, 2.5in ≈ 619 chars.
//
// Strips all other tags and counts visible characters.
// Used for greedy page-packing and column balancing.
func npEstChars(h string) int {
	imgTags := imgTagRe.FindAllString(h, -1)
	imgCost := 0

	const colWidthIn = 3.3   // column width in inches
	const maxHeightIn = 2.5  // CSS max-height cap
	const charsPerIn = 247.0 // 48 chars/line ÷ 0.194 in/line

	for _, tag := range imgTags {
		// Extract width and height attributes
		wMatch := imgWidthRe.FindStringSubmatch(tag)
		hMatch := imgHeightRe.FindStringSubmatch(tag)

		if len(wMatch) > 1 && len(hMatch) > 1 {
			var w, h float64
			fmt.Sscanf(wMatch[1], "%f", &w)
			fmt.Sscanf(hMatch[1], "%f", &h)

			if w > 0 && h > 0 {
				// Calculate actual rendered height: scale to column width, cap at max
				aspectRatio := h / w
				renderedHeight := colWidthIn * aspectRatio
				if renderedHeight > maxHeightIn {
					renderedHeight = maxHeightIn
				}
				imgCost += int(renderedHeight * charsPerIn)
				continue
			}
		}

		// No dimensions found: assume max height (conservative estimate)
		imgCost += 619 // int(2.5in * 247 chars/in)
	}

	stripped := htmlTagRe.ReplaceAllString(h, "")
	return len(stripped) + imgCost
}

// npTOCHTML builds the IN THIS EDITION TOC box HTML.
func npTOCHTML(articles []*art.Article) string {
	var sb strings.Builder
	sb.WriteString("<div class=\"toc\">\n")
	sb.WriteString("  <h2>IN THIS EDITION</h2>\n")
	sb.WriteString("  <ul>\n")
	for i, a := range articles {
		sb.WriteString("    <li>\n")
		sb.WriteString(fmt.Sprintf("      <a href=\"#article-%d\">\n", i+1))
		sb.WriteString(fmt.Sprintf("        <span class=\"toc-title\">%s</span>\n", html.EscapeString(a.Title)))
		var parts []string
		if a.Author != "" {
			parts = append(parts, html.EscapeString(a.Author))
		}
		if a.Publication != "" {
			parts = append(parts, html.EscapeString(a.Publication))
		}
		if len(parts) > 0 {
			sb.WriteString(fmt.Sprintf("        <span class=\"toc-byline\">%s</span>\n", strings.Join(parts, ", ")))
		}
		sb.WriteString("      </a>\n")
		sb.WriteString("    </li>\n")
	}
	sb.WriteString("  </ul>\n")
	sb.WriteString("</div>\n")
	return sb.String()
}

// pagePart couples a rendered HTML snippet with its estimated visible-character
// count. Used to pack content into pages (buildNewspaper) and to balance
// content across the 3 table columns (distributeToColumns).
type pagePart struct {
	html  string
	chars int
}

// distributeToColumns distributes pageParts into numCols table columns,
// balancing content by estimated character count.
// distributeToColumns distributes pageParts into numCols table columns,
// balancing content by estimated character count.
//
// Two-phase approach:
//  1. Greedy forward pass: fill each column up to total/numCols chars.
//  2. Rebalancing: up to 5 passes moving the last part of a heavier column
//     to the front of the next column when that reduces the imbalance.
//     Zero-cost parts (e.g. <hr> separators) are never moved.
func distributeToColumns(parts []pagePart, numCols int) [][]pagePart {
	cols := make([][]pagePart, numCols)
	if len(parts) == 0 {
		return cols
	}
	total := 0
	for _, p := range parts {
		total += p.chars
	}
	if total == 0 {
		cols[0] = parts
		return cols
	}

	// Phase 1: greedy forward pass
	// Add parts to current column until adding the next part would make
	// the column further from the target than it currently is.
	target := total / numCols
	curCol := 0
	colUsed := 0

	abs := func(x int) int {
		if x < 0 {
			return -x
		}
		return x
	}

	for _, p := range parts {
		if curCol < numCols-1 && colUsed > 0 {
			// Calculate imbalance before and after adding this part
			currentDiff := abs(colUsed - target)
			afterDiff := abs(colUsed + p.chars - target)

			// If adding this part makes us further from target, move to next column
			if afterDiff > currentDiff && colUsed >= target/2 {
				curCol++
				colUsed = 0
			}
		}
		cols[curCol] = append(cols[curCol], p)
		colUsed += p.chars
	}

	// Phase 2: rebalancing — move last non-zero-cost part of a heavier column
	// to the front of the next column if that reduces the absolute difference.
	colSum := func(c []pagePart) int {
		s := 0
		for _, p := range c {
			s += p.chars
		}
		return s
	}
	iabs := func(x int) int {
		if x < 0 {
			return -x
		}
		return x
	}
	for pass := 0; pass < 5; pass++ {
		moved := false
		for c := 0; c < numCols-1; c++ {
			if len(cols[c]) == 0 {
				continue
			}
			// Find the last part with non-zero cost
			lastIdx := len(cols[c]) - 1
			for lastIdx >= 0 && cols[c][lastIdx].chars == 0 {
				lastIdx--
			}
			if lastIdx < 0 {
				continue
			}
			sumC := colSum(cols[c])
			sumNext := colSum(cols[c+1])
			if sumC <= sumNext {
				continue // already balanced or next is heavier
			}
			last := cols[c][lastIdx]
			newSumC := sumC - last.chars
			newSumNext := sumNext + last.chars
			if iabs(newSumC-newSumNext) < iabs(sumC-sumNext) {
				// Move: remove from cols[c], prepend to cols[c+1]
				cols[c] = append(cols[c][:lastIdx], cols[c][lastIdx+1:]...)
				cols[c+1] = append([]pagePart{last}, cols[c+1]...)
				moved = true
			}
		}
		if !moved {
			break
		}
	}
	return cols
}

// buildNewspaperData packs articles into pages and returns the npData struct
// consumed by templates/newspaper.gohtml.
//
// Algorithm:
//  1. Build a flat list of chunks (article headers + individual block elements).
//  2. Greedily pack chunks into pages by estimated character count.
//     npEstChars counts each <img> as 200 chars to represent its visual height.
//  3. Each page distributes its chunks into 3 columns by char count.
//  4. page-break-before: always (newspaper-page CSS) forces one physical page each.
//
// CSS column-count is NOT used: Qt WebKit 5.15 in wkhtmltopdf does not
// reliably activate it. Table-based columns work without any special tricks.
func buildNewspaperData(articles []*art.Article, cssURL template.URL, title, subtitle string) npData {
	// Page capacity in estimated visible characters (images counted by actual
	// aspect ratio; text at 10pt/48 chars per line on a 3.3in column).
	// US Letter landscape, 0.5in margins → 10in × 7.5in usable.
	// Page 0: masthead (~1.5in) leaves ~6in for content.
	//   6in / 0.194in/line × 48 chars × 3 cols = 4464; use 90% → 4000
	// Other pages: full 7.5in usable.
	//   7.5in / 0.194in/line × 48 chars × 3 cols = 5572; use 100% → 5600
	const capFirst = 4000
	const capOther = 5600

	type chunk struct {
		artNum   int    // 1-based article number
		artTitle string // for "continued" labels
		isHeader bool   // true = article header block
		html     string // HTML for this chunk
		chars    int    // estimated visible chars
	}

	var chunks []chunk
	for i, a := range articles {
		headerHTML := renderArticleHeader(a, i+1)
		chunks = append(chunks, chunk{
			artNum:   i + 1,
			artTitle: a.Title,
			isHeader: true,
			html:     headerHTML,
			chars:    npEstChars(headerHTML),
		})

		content := a.Content
		if a.RemoveImages {
			if cleaned, _, err := clean.RemoveAllImages(content); err == nil {
				content = cleaned
			}
		}

		// Extract top-level block elements (handles Substack outer wrapper divs).
		// Each block is self-contained — no unclosed parent divs that would nest
		// .newspaper-page divs inside each other and break page-break-before.
		blocks := clean.ExtractBlocks(content)
		for _, blk := range blocks {
			chunks = append(chunks, chunk{
				artNum:   i + 1,
				artTitle: a.Title,
				isHeader: false,
				html:     blk,
				chars:    npEstChars(blk),
			})
		}
		chunks = append(chunks, chunk{
			artNum:   i + 1,
			artTitle: a.Title,
			html:     "<hr class=\"article-sep\">\n",
			chars:    0, // zero so a separator never triggers a page flush alone
		})
	}

	// Greedily pack chunks into pages.
	type rawPage struct {
		first bool
		parts []pagePart
	}
	var rawPages []rawPage
	cur := rawPage{first: true}
	tocHTML := npTOCHTML(articles)
	// Use the actual estimated size of the TOC (not a fixed column reservation)
	// so the remaining space in column 1 can be filled with first-article content.
	tocCost := npEstChars(tocHTML)
	cur.parts = append(cur.parts, pagePart{html: tocHTML, chars: tocCost})
	curUsed := tocCost
	curCap := capFirst

	for _, c := range chunks {
		if curUsed+c.chars > curCap && len(cur.parts) > 0 && c.chars > 0 {
			rawPages = append(rawPages, cur)
			cur = rawPage{first: false}
			curUsed = 0
			curCap = capOther
			if !c.isHeader {
				contLabel := fmt.Sprintf(
					"<p class=\"article-cont-title\">%s (continued)</p>",
					html.EscapeString(c.artTitle),
				)
				cur.parts = append(cur.parts, pagePart{html: contLabel, chars: 60})
				curUsed += 60
			}
		}
		cur.parts = append(cur.parts, pagePart{html: c.html, chars: c.chars})
		curUsed += c.chars
	}
	if len(cur.parts) > 0 {
		rawPages = append(rawPages, cur)
	}

	// Widow-page merge: if a non-first page has fewer than 15% of capOther chars
	// it would render as a nearly-blank page. Fold its parts back into the
	// previous page (allowing a slight over-capacity) so no page is mostly empty.
	const minPageChars = capOther / 7 // ~770 chars
	for i := len(rawPages) - 1; i > 0; i-- {
		total := 0
		for _, p := range rawPages[i].parts {
			total += p.chars
		}
		if total < minPageChars {
			rawPages[i-1].parts = append(rawPages[i-1].parts, rawPages[i].parts...)
			rawPages = append(rawPages[:i], rawPages[i+1:]...)
		}
	}

	// Convert raw pages into npPage structs for the template.
	pages := make([]npPage, len(rawPages))
	for i, pg := range rawPages {
		cls := "newspaper-page"
		if pg.first {
			cls += " newspaper-page-first"
		}
		dist := distributeToColumns(pg.parts, 3)
		ncols := make([]npColumn, len(dist))
		for j, col := range dist {
			parts := make([]template.HTML, len(col))
			for k, part := range col {
				parts[k] = template.HTML(part.html)
			}
			ncols[j] = npColumn{Parts: parts}
		}
		pages[i] = npPage{Class: cls, Columns: ncols}
	}

	return npData{
		CSSPath:  cssURL,
		Title:    title,
		Subtitle: subtitle,
		Pages:    pages,
	}
}

// buildEssayData assembles the essayData struct consumed by templates/essay.gohtml.
func buildEssayData(articles []*art.Article, cssURL template.URL, title, subtitle string) essayData {
	toc := make([]essayTOCEntry, len(articles))
	for i, a := range articles {
		toc[i] = essayTOCEntry{
			Num:         i + 1,
			Title:       a.Title,
			Author:      a.Author,
			Publication: a.Publication,
		}
	}
	arts := make([]template.HTML, len(articles))
	for i, a := range articles {
		arts[i] = template.HTML(renderArticle(a, i+1))
	}
	return essayData{
		CSSPath:  cssURL,
		Title:    title,
		Subtitle: subtitle,
		TOC:      toc,
		Articles: arts,
	}
}

// renderArticleHeader generates just the header block for an article (title,
// subtitle, meta). Used by buildNewspaper to treat the header as an
// unbreakable chunk that must not be split from the first paragraph.
// renderArticleHeader generates a self-contained article header block.
// It closes all opened divs so it never leaves unclosed tags in a page section.
func renderArticleHeader(a *art.Article, num int) string {
	var sb strings.Builder
	sb.WriteString(fmt.Sprintf("<div class=\"article-header\" id=\"article-%d\">\n", num))
	sb.WriteString(fmt.Sprintf("  <h2 class=\"article-title\">%s</h2>\n", html.EscapeString(a.Title)))
	if a.Subtitle != "" {
		sb.WriteString(fmt.Sprintf("  <h3 class=\"article-subtitle\">%s</h3>\n", html.EscapeString(a.Subtitle)))
	}
	meta := []string{}
	if a.Author != "" {
		meta = append(meta, fmt.Sprintf("By %s", html.EscapeString(a.Author)))
	}
	if a.Publication != "" {
		meta = append(meta, html.EscapeString(a.Publication))
	}
	if !a.PubDate.IsZero() {
		meta = append(meta, a.PubDate.Format("January 2, 2006"))
	}
	if len(meta) > 0 {
		sb.WriteString(fmt.Sprintf("  <p class=\"article-meta\">%s</p>\n", strings.Join(meta, " • ")))
	}
	sb.WriteString("</div>\n")
	return sb.String()
}

// renderArticle generates the HTML for a single article section.
func renderArticle(a *art.Article, num int) string {
	var sb strings.Builder

	sb.WriteString(fmt.Sprintf("<div class=\"article\" id=\"article-%d\">\n", num))

	// Article header
	sb.WriteString("  <div class=\"article-header\">\n")
	sb.WriteString(fmt.Sprintf("    <h2 class=\"article-title\">%s</h2>\n", html.EscapeString(a.Title)))

	if a.Subtitle != "" {
		sb.WriteString(fmt.Sprintf("    <h3 class=\"article-subtitle\">%s</h3>\n", html.EscapeString(a.Subtitle)))
	}

	// Metadata line
	meta := []string{}
	if a.Author != "" {
		meta = append(meta, fmt.Sprintf("By %s", html.EscapeString(a.Author)))
	}
	if a.Publication != "" {
		meta = append(meta, html.EscapeString(a.Publication))
	}
	if !a.PubDate.IsZero() {
		meta = append(meta, a.PubDate.Format("January 2, 2006"))
	}
	if len(meta) > 0 {
		sb.WriteString(fmt.Sprintf("    <p class=\"article-meta\">%s</p>\n", strings.Join(meta, " • ")))
	}

	sb.WriteString("  </div>\n\n")

	// Article content (already HTML)
	// Apply per-article image removal if requested
	articleContent := a.Content
	if a.RemoveImages {
		cleanedContent, _, err := clean.RemoveAllImages(a.Content)
		if err == nil {
			articleContent = cleanedContent
		} else {
			// If cleaning fails, log but use original content
			fmt.Printf("Warning: Failed to remove images from article '%s': %v\n", a.Title, err)
		}
	}

	sb.WriteString("  <div class=\"article-content\">\n")
	sb.WriteString(articleContent)
	sb.WriteString("\n  </div>\n")

	sb.WriteString("</div>\n\n")

	return sb.String()
}
