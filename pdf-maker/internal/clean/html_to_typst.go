package clean

import (
	"fmt"
	"strings"

	"github.com/PuerkitoBio/goquery"
)

// HTMLToTypst converts an HTML fragment (article body) into Typst markup.
// It handles the common elements produced by Substack and other newsletter
// platforms: paragraphs, headings, blockquotes, lists, images, links, and
// inline formatting.
//
// Images are rendered as #image("<absPath>", width: 100%) using the absolute
// filesystem path already written by the media downloader. When removeImages
// is true all <img> elements are silently skipped.
func HTMLToTypst(htmlContent string, removeImages bool) (string, error) {
	if strings.TrimSpace(htmlContent) == "" {
		return "", nil
	}

	doc, err := goquery.NewDocumentFromReader(strings.NewReader("<div id=\"__root\">" + htmlContent + "</div>"))
	if err != nil {
		return "", fmt.Errorf("parse html: %w", err)
	}

	var sb strings.Builder
	convertNode(doc.Find("#__root"), &sb, removeImages)
	return strings.TrimSpace(sb.String()), nil
}

// convertNode walks a goquery selection and emits Typst markup into sb.
func convertNode(sel *goquery.Selection, sb *strings.Builder, removeImages bool) {
	sel.Contents().Each(func(_ int, s *goquery.Selection) {
		emitNode(s, sb, removeImages)
	})
}

// emitNode emits a single node (element or text) as Typst markup.
func emitNode(s *goquery.Selection, sb *strings.Builder, removeImages bool) {
	if goquery.NodeName(s) == "#text" {
		text := s.Text()
		if text != "" {
			sb.WriteString(escapeTypst(text))
		}
		return
	}

	tag := goquery.NodeName(s)
	switch tag {
	case "p":
		var inner strings.Builder
		convertNode(s, &inner, removeImages)
		body := strings.TrimSpace(inner.String())
		if body != "" {
			sb.WriteString(body)
			sb.WriteString("\n\n")
		}

	case "h1":
		var inner strings.Builder
		convertNode(s, &inner, removeImages)
		body := strings.TrimSpace(inner.String())
		if body != "" {
			sb.WriteString("= ")
			sb.WriteString(body)
			sb.WriteString("\n\n")
		}

	case "h2":
		var inner strings.Builder
		convertNode(s, &inner, removeImages)
		body := strings.TrimSpace(inner.String())
		if body != "" {
			// h2 in article body → level 3 in Typst (below the depth:2 outline cap)
			sb.WriteString("=== ")
			sb.WriteString(body)
			sb.WriteString("\n\n")
		}

	case "h3":
		var inner strings.Builder
		convertNode(s, &inner, removeImages)
		body := strings.TrimSpace(inner.String())
		if body != "" {
			// Level 4 in Typst (====(level4)) so it stays below the outline
			// depth-2 cap and doesn't appear in the Contents.
			sb.WriteString("==== ")
			sb.WriteString(body)
			sb.WriteString("\n\n")
		}

	case "h4", "h5", "h6":
		var inner strings.Builder
		convertNode(s, &inner, removeImages)
		body := strings.TrimSpace(inner.String())
		if body != "" {
			sb.WriteString("===== ")
			sb.WriteString(body)
			sb.WriteString("\n\n")
		}

	case "blockquote":
		var inner strings.Builder
		convertNode(s, &inner, removeImages)
		body := strings.TrimSpace(inner.String())
		if body != "" {
			// Typst block quote using a box with left border accent
			sb.WriteString("#block(stroke: (left: 2pt + gray), inset: (left: 8pt, y: 4pt))[\n")
			sb.WriteString(body)
			sb.WriteString("\n]\n\n")
		}

	case "ul":
		s.Children().Each(func(_ int, li *goquery.Selection) {
			if goquery.NodeName(li) != "li" {
				return
			}
			var inner strings.Builder
			convertNode(li, &inner, removeImages)
			body := strings.TrimSpace(inner.String())
			if body != "" {
				sb.WriteString("- ")
				sb.WriteString(body)
				sb.WriteString("\n")
			}
		})
		sb.WriteString("\n")

	case "ol":
		n := 1
		s.Children().Each(func(_ int, li *goquery.Selection) {
			if goquery.NodeName(li) != "li" {
				return
			}
			var inner strings.Builder
			convertNode(li, &inner, removeImages)
			body := strings.TrimSpace(inner.String())
			if body != "" {
				sb.WriteString(fmt.Sprintf("%d. ", n))
				sb.WriteString(body)
				sb.WriteString("\n")
				n++
			}
		})
		sb.WriteString("\n")

	case "img":
		if removeImages {
			return
		}
		src, exists := s.Attr("src")
		if !exists || src == "" {
			return
		}
		alt, _ := s.Attr("alt")
		sb.WriteString(fmt.Sprintf("#figure(\n  image(%q, width: 100%%),\n", src))
		if alt != "" {
			sb.WriteString(fmt.Sprintf("  caption: [%s],\n", escapeTypst(alt)))
		}
		sb.WriteString(")\n\n")

	case "figure":
		// Substack wraps images in <figure> with optional <figcaption>
		img := s.Find("img").First()
		caption := strings.TrimSpace(s.Find("figcaption").Text())
		if img.Length() > 0 && !removeImages {
			src, exists := img.Attr("src")
			if exists && src != "" {
				sb.WriteString(fmt.Sprintf("#figure(\n  image(%q, width: 100%%),\n", src))
				if caption != "" {
					sb.WriteString(fmt.Sprintf("  caption: [%s],\n", escapeTypst(caption)))
				}
				sb.WriteString(")\n\n")
			}
		}

	case "strong", "b":
		var inner strings.Builder
		convertNode(s, &inner, removeImages)
		body := strings.TrimSpace(inner.String())
		if body != "" {
			// Use #strong[...] function form (not *...*) so that whitespace
			// before/after the tag boundary does not affect parsing.
			sb.WriteString("#strong[")
			sb.WriteString(body)
			sb.WriteString("];")
		}

	case "em", "i":
		var inner strings.Builder
		convertNode(s, &inner, removeImages)
		body := strings.TrimSpace(inner.String())
		if body != "" {
			// Use #emph[...] function form (not _..._) so that e.g.
			// "the<em>Shareholder Republic</em>" does not produce "the_Shareholder
			// Republic_" where Typst refuses to open emphasis after a letter.
			sb.WriteString("#emph[")
			sb.WriteString(body)
			sb.WriteString("];")
		}

	case "a":
		var inner strings.Builder
		convertNode(s, &inner, removeImages)
		body := strings.TrimSpace(inner.String())
		href, _ := s.Attr("href")
		if body == "" {
			body = href
		}
		if href != "" && href != body {
			// Append ";" to explicitly terminate the #link expression.
			// In Typst markup mode, after any #expr, a following "(" is
			// greedily consumed as a call suffix on the expression's result —
			// even after #{...} or #func(args) forms. The only reliable
			// escape hatch is a semicolon, which terminates the hash
			// expression and is never included in rendered output.
			// Example: "#link("u")[t];(more)" renders as link + "(more)".
			sb.WriteString(fmt.Sprintf("#link(%q)[%s];", href, body))
		} else {
			sb.WriteString(body)
		}

	case "br":
		sb.WriteString(" \\\n")

	case "hr":
		sb.WriteString("\n#line(length: 100%, stroke: 0.5pt)\n\n")

	case "code":
		var inner strings.Builder
		convertNode(s, &inner, removeImages)
		body := inner.String()
		if body != "" {
			sb.WriteString("`")
			sb.WriteString(body)
			sb.WriteString("`")
		}

	case "pre":
		var inner strings.Builder
		// For pre, collect raw text
		inner.WriteString(s.Text())
		body := inner.String()
		if body != "" {
			sb.WriteString("```\n")
			sb.WriteString(body)
			sb.WriteString("\n```\n\n")
		}

	case "sup":
		// Substack footnote superscripts
		var inner strings.Builder
		convertNode(s, &inner, removeImages)
		body := strings.TrimSpace(inner.String())
		if body != "" {
			sb.WriteString(fmt.Sprintf("#super[%s]", body))
		}

	case "sub":
		var inner strings.Builder
		convertNode(s, &inner, removeImages)
		body := strings.TrimSpace(inner.String())
		if body != "" {
			sb.WriteString(fmt.Sprintf("#sub[%s]", body))
		}

	case "span":
		// Pass through span contents; styling from class is ignored (intentional)
		convertNode(s, sb, removeImages)

	case "div":
		// Generic div: recurse into children, adding a paragraph break after
		var inner strings.Builder
		convertNode(s, &inner, removeImages)
		body := strings.TrimSpace(inner.String())
		if body != "" {
			sb.WriteString(body)
			if !strings.HasSuffix(body, "\n\n") {
				sb.WriteString("\n\n")
			}
		}

	case "table":
		// Best-effort table conversion
		emitTable(s, sb, removeImages)

	default:
		// Unknown element: recurse into children
		convertNode(s, sb, removeImages)
	}
}

// emitTable converts a basic HTML table to Typst table syntax.
func emitTable(s *goquery.Selection, sb *strings.Builder, removeImages bool) {
	var rows [][]string
	s.Find("tr").Each(func(_ int, tr *goquery.Selection) {
		var row []string
		tr.Find("th, td").Each(func(_ int, td *goquery.Selection) {
			var cell strings.Builder
			convertNode(td, &cell, removeImages)
			row = append(row, strings.TrimSpace(cell.String()))
		})
		if len(row) > 0 {
			rows = append(rows, row)
		}
	})
	if len(rows) == 0 {
		return
	}

	// Determine column count from first row
	cols := len(rows[0])
	if cols == 0 {
		return
	}

	sb.WriteString(fmt.Sprintf("#table(\n  columns: %d,\n", cols))
	for _, row := range rows {
		for _, cell := range row {
			sb.WriteString(fmt.Sprintf("  [%s],\n", cell))
		}
	}
	sb.WriteString(")\n\n")
}

// escapeTypst escapes characters that have special meaning in Typst markup.
// Reference: https://typst.app/docs/reference/syntax/
func escapeTypst(s string) string {
	// Typst special characters that need escaping in content:
	// \ # $ @ _ * ` < > =
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
		default:
			sb.WriteRune(r)
		}
	}
	return sb.String()
}
