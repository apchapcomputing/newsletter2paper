package pdf

import (
	"fmt"
	"strings"
	"time"

	art "pdf-maker/internal/article"
	"pdf-maker/internal/clean"
)

// AssembleNewspaperTypst builds a complete Typst (.typ) document for the newspaper layout.
//
// The document uses Typst's native columns: 3 page setting so no manual
// column-packing is needed — the Typst typesetter handles balancing
// automatically and correctly across page boundaries.
//
// Structure:
//   - Page settings (US Letter landscape, 3 columns, 0.75in margins)
//   - Font + paragraph settings matching the prototype in typst.typ
//   - Floating masthead: title, date/article-count line, rule
//   - Table of contents (#outline())
//   - Per-article sections: heading with byline, then body content
func AssembleNewspaperTypst(articles []*art.Article, title string) (string, error) {
	if len(articles) == 0 {
		return "", fmt.Errorf("no articles provided")
	}

	articleCount := len(articles)
	articleWord := "Articles"
	if articleCount == 1 {
		articleWord = "Article"
	}
	dateLine := fmt.Sprintf("%s #h(2em) %d %s",
		time.Now().Format("Monday, January 2, 2006"),
		articleCount,
		articleWord,
	)

	var sb strings.Builder

	// ── Page & text settings ────────────────────────────────────────────────
	sb.WriteString(`#import "@preview/droplet:0.3.1": dropcap

#set page(
  paper: "us-letter",
  flipped: true,
  margin: (x: 0.75in, y: 0.75in),
  columns: 3,
)

#set text(
  font: ("Linux Libertine O", "Libertinus Serif", "Liberation Serif", "DejaVu Serif", "Noto Color Emoji"),
  size: 10pt,
)

#set par(
  justify: true,
  leading: 0.65em,
)

// Article title headings: larger, bolder, with more vertical breathing room
#show heading.where(level: 2): it => {
  v(0.6em, weak: true)
  block(above: 0.8em, below: 0.5em,
    text(size: 13pt, weight: "extrabold", it.body)
  )
}
#show heading.where(level: 3): it => {
  v(0.4em, weak: true)
  block(above: 0.4em, below: 0.3em, it)
}

`)

	// ── Floating masthead ───────────────────────────────────────────────────
	sb.WriteString("#place(\n")
	sb.WriteString("  top + center,\n")
	sb.WriteString("  scope: \"parent\",\n")
	sb.WriteString("  float: true,\n")
	sb.WriteString("  {\n")
	sb.WriteString("    align(center)[\n")
	sb.WriteString(fmt.Sprintf("      #text(size: 28pt, weight: \"bold\")[%s]\n", escapeTypstContent(title)))
	sb.WriteString("      #v(0.05em)\n")
	sb.WriteString(fmt.Sprintf("      #text(size: 9pt, style: \"italic\")[\n        %s\n      ]\n", dateLine))
	sb.WriteString("      #v(0.2em)\n")
	sb.WriteString("      #line(length: 100%, stroke: 1.2pt)\n")
	sb.WriteString("      #v(0.2em)\n")
	sb.WriteString("    ]\n")
	sb.WriteString("  }\n")
	sb.WriteString(")\n\n")

	// ── Table of contents (bordered box) ────────────────────────────────────
	sb.WriteString("#rect(stroke: 0.5pt, inset: (x: 0.8em, y: 0.7em), width: 100%, radius: 2pt)[\n")
	sb.WriteString("#v(0.1em)\n")
	sb.WriteString("#align(center)[#text(size: 12pt, weight: \"medium\")[IN THIS EDITION]]\n")
	sb.WriteString("#v(0.3em)\n")
	sb.WriteString("#line(length: 100%, stroke: 0.4pt)\n")
	sb.WriteString("#v(0.3em)\n")
	for i, a := range articles {
		label := fmt.Sprintf("article-%d", i+1)
		title := escapeTypstContent(a.Title)
		var bp []string
		if a.Author != "" {
			bp = append(bp, escapeTypstContent(a.Author))
		}
		if a.Publication != "" {
			bp = append(bp, escapeTypstContent(a.Publication))
		}
		byline := strings.Join(bp, " · ")
		if byline != "" {
			sb.WriteString(fmt.Sprintf(
				"#link(<%s>)[*%s*]\\\n#text(size: 8pt, fill: gray, style: \"italic\")[%s]\n\n",
				label, title, byline))
		} else {
			sb.WriteString(fmt.Sprintf("#link(<%s>)[*%s*]\n\n", label, title))
		}
	}
	sb.WriteString("]\n")
	sb.WriteString("#v(0.5em)\n\n")

	// ── Articles ────────────────────────────────────────────────────────────
	for i, a := range articles {
		// Labelled heading so the TOC #link(<article-N>) can target it
		sb.WriteString(fmt.Sprintf("== %s <article-%d>\n\n", escapeTypstContent(a.Title), i+1))

		// Byline
		var bylineParts []string
		if a.Author != "" {
			bylineParts = append(bylineParts, a.Author)
		}
		if a.Publication != "" {
			bylineParts = append(bylineParts, a.Publication)
		}
		if !a.PubDate.IsZero() {
			bylineParts = append(bylineParts, a.PubDate.Format("January 2, 2006"))
		}
		if len(bylineParts) > 0 {
			sb.WriteString(fmt.Sprintf("#text(size: 8pt, style: \"italic\")[%s]\n\n",
				escapeTypstContent(strings.Join(bylineParts, " · "))))
		}

		// Article body
		body, err := clean.HTMLToTypst(a.Content, a.RemoveImages)
		if err != nil {
			// Non-fatal: emit a note and continue
			sb.WriteString(fmt.Sprintf("#text(fill: red)[Error rendering article: %s]\n\n",
				escapeTypstContent(err.Error())))
		} else if body != "" {
			sb.WriteString(addDropCap(body))
			sb.WriteString("\n\n")
		}

		// Article separator (skip after last article)
		if i < len(articles)-1 {
			sb.WriteString("#v(1.2em)\n")
			sb.WriteString("#line(length: 100%, stroke: (paint: gray, thickness: 0.5pt, dash: \"dashed\"))\n")
			sb.WriteString("#v(0.8em)\n\n")
		}
	}

	return sb.String(), nil
}

// AssembleEssayTypst builds a complete Typst (.typ) document for the essay layout.
//
// Portrait US Letter, single column, generous margins, 12pt serif body text.
// No drop caps. Same floating masthead and bordered TOC box as the newspaper
// layout, but without flipped: true or columns: 3.
func AssembleEssayTypst(articles []*art.Article, title string) (string, error) {
	if len(articles) == 0 {
		return "", fmt.Errorf("no articles provided")
	}

	articleCount := len(articles)
	articleWord := "Articles"
	if articleCount == 1 {
		articleWord = "Article"
	}
	dateLine := fmt.Sprintf("%s • %d %s",
		time.Now().Format("Monday, January 2, 2006"),
		articleCount,
		articleWord,
	)

	var sb strings.Builder

	// ── Page & text settings ────────────────────────────────────────────────
	sb.WriteString(`#import "@preview/droplet:0.3.1": dropcap

#set page(
  paper: "us-letter",
  margin: (x: 1in, y: 0.75in),
)

#set text(
  font: ("Linux Libertine O", "Libertinus Serif", "Liberation Serif", "DejaVu Serif", "Noto Color Emoji"),
  size: 12pt,
)

#set par(
  justify: true,
  leading: 0.8em,
  first-line-indent: 1.2em,
)

#show heading.where(level: 2): it => {
  v(1.2em, weak: true)
  block(above: 1em, below: 0.5em,
    text(size: 16pt, weight: "extrabold", it.body)
  )
}
#show heading.where(level: 3): it => {
  v(0.6em, weak: true)
  block(above: 0.6em, below: 0.4em,
    text(size: 13pt, weight: "bold", it.body)
  )
}

`)

	// ── Floating masthead ───────────────────────────────────────────────────
	sb.WriteString("#place(\n")
	sb.WriteString("  top + center,\n")
	sb.WriteString("  scope: \"parent\",\n")
	sb.WriteString("  float: true,\n")
	sb.WriteString("  {\n")
	sb.WriteString("    align(center)[\n")
	sb.WriteString(fmt.Sprintf("      #text(size: 32pt, weight: \"bold\")[%s]\n", escapeTypstContent(title)))
	sb.WriteString("      #v(-0.5em)\n")
	sb.WriteString(fmt.Sprintf("      #text(size: 10pt, style: \"italic\")[\n        %s\n      ]\n", dateLine))
	sb.WriteString("      #v(0.2em)\n")
	sb.WriteString("      #line(length: 100%, stroke: 1.5pt)\n")
	sb.WriteString("      #v(0.2em)\n")
	sb.WriteString("    ]\n")
	sb.WriteString("  }\n")
	sb.WriteString(")\n\n")

	// ── Table of contents (bordered box) ────────────────────────────────────
	// sb.WriteString("#rect(stroke: 0.5pt, inset: (x: 0.8em, y: 0.7em), width: 100%, radius: 2pt)[\n")
	// sb.WriteString("#v(0.2em)\n")
	// sb.WriteString("#align(center)[#text(size: 12pt, weight: \"medium\")[IN THIS EDITION]]\n")
	// sb.WriteString("#v(0.1em)\n")
	// sb.WriteString("#line(length: 100%, stroke: 0.4pt)\n")
	// sb.WriteString("#v(0.2em)\n")
	// for i, a := range articles {
	// 	label := fmt.Sprintf("article-%d", i+1)
	// 	articleTitle := escapeTypstContent(a.Title)
	// 	var bp []string
	// 	if a.Author != "" {
	// 		bp = append(bp, escapeTypstContent(a.Author))
	// 	}
	// 	if a.Publication != "" {
	// 		bp = append(bp, escapeTypstContent(a.Publication))
	// 	}
	// 	byline := strings.Join(bp, " · ")
	// 	if byline != "" {
	// 		sb.WriteString(fmt.Sprintf(
	// 			"#link(<%s>)[*%s*]\\\n#text(size: 9pt, fill: gray, style: \"italic\")[%s]\n\n",
	// 			label, articleTitle, byline))
	// 	} else {
	// 		sb.WriteString(fmt.Sprintf("#link(<%s>)[*%s*]\n\n", label, articleTitle))
	// 	}
	// }
	// sb.WriteString("]\n")
	// sb.WriteString("#v(1em)\n\n")

	// ── Articles ────────────────────────────────────────────────────────────
	for i, a := range articles {
		sb.WriteString(fmt.Sprintf("== %s <article-%d>\n\n", escapeTypstContent(a.Title), i+1))

		// Byline
		var bylineParts []string
		if a.Author != "" {
			bylineParts = append(bylineParts, a.Author)
		}
		if a.Publication != "" {
			bylineParts = append(bylineParts, a.Publication)
		}
		if !a.PubDate.IsZero() {
			bylineParts = append(bylineParts, a.PubDate.Format("January 2, 2006"))
		}
		if len(bylineParts) > 0 {
			sb.WriteString(fmt.Sprintf("#text(size: 9pt, style: \"italic\")[%s]\n\n",
				escapeTypstContent(strings.Join(bylineParts, " · "))))
		}

		// Article body — no drop cap for essay format
		body, err := clean.HTMLToTypst(a.Content, a.RemoveImages)
		if err != nil {
			sb.WriteString(fmt.Sprintf("#text(fill: red)[Error rendering article: %s]\n\n",
				escapeTypstContent(err.Error())))
		} else if body != "" {
			sb.WriteString(body)
			sb.WriteString("\n\n")
		}

		// Article separator (skip after last article)
		if i < len(articles)-1 {
			sb.WriteString("#v(2em)\n")
			sb.WriteString("#line(length: 100%, stroke: (paint: gray, thickness: 0.5pt))\n")
			sb.WriteString("#v(1em)\n\n")
		}
	}

	return sb.String(), nil
}

// escapeTypstContent escapes a plain-text string for use as Typst content
// (inside square brackets or directly in the document body).
// Only characters that are syntactically special in Typst content need escaping.
func escapeTypstContent(s string) string {
	var sb strings.Builder
	sb.Grow(len(s))
	for _, r := range s {
		switch r {
		case '\\':
			sb.WriteString(`\\`)
		case '#':
			sb.WriteString(`\#`)
		case '$':
			sb.WriteString(`\$`)
		case '@':
			sb.WriteString(`\@`)
		case '_':
			sb.WriteString(`\_`)
		case '*':
			sb.WriteString(`\*`)
		case '`':
			sb.WriteString("\\`")
		case '<':
			sb.WriteString(`\<`)
		case '>':
			sb.WriteString(`\>`)
		case '=':
			sb.WriteString(`\=`)
		case '[':
			sb.WriteString(`\[`)
		case ']':
			sb.WriteString(`\]`)
		default:
			sb.WriteRune(r)
		}
	}
	return sb.String()
}

// addDropCap wraps the first body-text paragraph with the droplet package's
// #dropcap() function, which automatically extracts the first letter, scales
// it to the given line height, and splits the paragraph text to wrap around it.
//
// The first paragraph is often short (one sentence), so we absorb the next
// plain-text paragraph into the dropcap content as well. This gives the
// splitter enough text to fill all 3 lines beside the drop cap, so lines 2
// and 3 visually wrap under line 1 rather than jumping to full column width.
func addDropCap(body string) string {
	paragraphs := strings.Split(body, "\n\n")
	for i, para := range paragraphs {
		trimmed := strings.TrimSpace(para)
		if trimmed == "" {
			continue
		}
		// Skip headings and Typst directives
		if strings.HasPrefix(trimmed, "=") || strings.HasPrefix(trimmed, "#") {
			continue
		}
		if len([]rune(trimmed)) == 0 {
			continue
		}

		// Absorb the next plain-text paragraph so the drop cap has enough text
		// to fill its full height (3 lines) beside the capital letter.
		content := trimmed
		consumed := i + 1
		for consumed < len(paragraphs) {
			next := strings.TrimSpace(paragraphs[consumed])
			if next == "" {
				consumed++
				continue
			}
			if strings.HasPrefix(next, "=") || strings.HasPrefix(next, "#") {
				break
			}
			content += "\n" + next
			consumed++
			break
		}

		dropcap := "#dropcap(height: 3, gap: 4pt, overhang: 6pt, font: \"Linux Libertine O\", weight: \"extrabold\")[\n" +
			content + "\n]"

		result := append([]string{}, paragraphs[:i]...)
		result = append(result, dropcap)
		result = append(result, paragraphs[consumed:]...)
		return strings.Join(result, "\n\n")
	}
	return body
}
