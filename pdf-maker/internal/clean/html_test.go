package clean

import (
	"strings"
	"testing"
)

func mustClean(t *testing.T, in string) (string, Stats) {
	t.Helper()
	out, stats, err := CleanHTML(in, false)
	if err != nil {
		t.Fatalf("CleanHTML: %v", err)
	}
	return out, stats
}

func TestCleanHTML_RemovesSubscriptionCallsToAction(t *testing.T) {
	in := `<p>Real paragraph.</p>
<div class="subscription-widget-wrap-editor"><form><input type="email"><button>Subscribe</button></form></div>
<div class="subscribe-footer">Subscribe now</div>
<p>Another paragraph.</p>`

	out, stats := mustClean(t, in)

	for _, gone := range []string{"Subscribe", "<form", "<input", "subscription-widget"} {
		if strings.Contains(out, gone) {
			t.Errorf("output still contains %q:\n%s", gone, out)
		}
	}
	for _, kept := range []string{"Real paragraph.", "Another paragraph."} {
		if !strings.Contains(out, kept) {
			t.Errorf("output lost %q:\n%s", kept, out)
		}
	}
	if stats.SubscriptionWidgets != 1 {
		t.Errorf("SubscriptionWidgets = %d, want 1", stats.SubscriptionWidgets)
	}
}

func TestCleanHTML_RemovesMediaPlayersAndEmbedControls(t *testing.T) {
	in := `<p>Listen below.</p>
<audio src="a.mp3"></audio>
<video src="v.mp4"></video>
<div data-component-name="AudioEmbedPlayer"><span>0:00</span></div>
<button aria-label="Link"><svg class="lucide-link"></svg></button>
<p>After the player.</p>`

	out, _ := mustClean(t, in)

	for _, gone := range []string{"<audio", "<video", "AudioEmbedPlayer", "<button"} {
		if strings.Contains(out, gone) {
			t.Errorf("output still contains %q:\n%s", gone, out)
		}
	}
	if !strings.Contains(out, "Listen below.") || !strings.Contains(out, "After the player.") {
		t.Errorf("surrounding text was lost:\n%s", out)
	}
}

// A single "▶" or "play" in prose must never cost the reader the whole article:
// newsletters are wrapped in a single container div, so an over-eager text match
// on ancestors deletes everything.
func TestCleanHTML_ProseMentioningPlaybackSymbolsSurvivesInsideWrapper(t *testing.T) {
	cases := map[string]string{
		"play symbol":  `<div class="body markup"><p>Press ▶ to start the tape.</p><p>Second paragraph.</p></div>`,
		"volume emoji": `<div class="body markup"><p>Turn it up 🔊 for the finale.</p><p>Second paragraph.</p></div>`,
		"aria display": `<div class="body markup" aria-label="Display settings"><p>Body text.</p><p>Second paragraph.</p></div>`,
	}
	for name, in := range cases {
		t.Run(name, func(t *testing.T) {
			out, _ := mustClean(t, in)
			if !strings.Contains(out, "Second paragraph.") {
				t.Errorf("article body was deleted:\n%s", out)
			}
		})
	}
}

func TestCleanHTML_PlainContentIsUntouched(t *testing.T) {
	in := `<h2>Heading</h2><p>Some <em>emphasised</em> text with a <a href="https://example.com">link</a>.</p><ul><li>one</li></ul>`

	out, stats := mustClean(t, in)

	if out != in {
		t.Errorf("clean content was modified:\n got: %s\nwant: %s", out, in)
	}
	if stats != (Stats{}) {
		t.Errorf("stats = %+v, want zero", stats)
	}
}

func TestCleanHTML_ReformatsSubstackFootnotesInline(t *testing.T) {
	in := `<p>Claim.</p>
<div class="footnote"><a class="footnote-number" id="footnote-1" href="#footnote-anchor-1">1</a><div class="footnote-content"><p>The source.</p></div></div>`

	out, stats := mustClean(t, in)

	if stats.FootnotesFormatted != 1 {
		t.Fatalf("FootnotesFormatted = %d, want 1\n%s", stats.FootnotesFormatted, out)
	}
	if strings.Contains(out, `class="footnote"`) {
		t.Errorf("original footnote block still present:\n%s", out)
	}
	if !strings.Contains(out, "1. ") || !strings.Contains(out, "The source.") {
		t.Errorf("footnote number or text missing:\n%s", out)
	}
}

func TestRemoveAllImages(t *testing.T) {
	in := `<p>Before.</p>
<figure><img src="a.png"><figcaption>cap</figcaption></figure>
<div class="captioned-image-container"><img src="b.png"></div>
<picture><source srcset="c.webp"><img src="c.png"></picture>
<p>After <img src="inline.png"> inline.</p>`

	out, removed, err := RemoveAllImages(in)
	if err != nil {
		t.Fatal(err)
	}

	if strings.Contains(out, "<img") || strings.Contains(out, "<figure") || strings.Contains(out, "<picture") {
		t.Errorf("image markup remains:\n%s", out)
	}
	if !strings.Contains(out, "Before.") || !strings.Contains(out, "After") {
		t.Errorf("text was lost:\n%s", out)
	}
	if removed < 3 {
		t.Errorf("removed = %d, want at least the 3 <img> tags that were not inside removed wrappers", removed)
	}
}

func TestExtractBlocks_UnwrapsSingleOuterDivAndKeepsTopLevelBlocks(t *testing.T) {
	in := `<div class="body markup"><p>One</p><h2>Two</h2><p>Three</p></div>`

	blocks := ExtractBlocks(in)

	want := []string{"<p>One</p>", "<h2>Two</h2>", "<p>Three</p>"}
	if len(blocks) != len(want) {
		t.Fatalf("got %d blocks %q, want %d", len(blocks), blocks, len(want))
	}
	for i := range want {
		if blocks[i] != want[i] {
			t.Errorf("block %d = %q, want %q", i, blocks[i], want[i])
		}
	}
}

func TestExtractBlocks_DoesNotUnwrapWhenThereAreSeveralTopLevelElements(t *testing.T) {
	blocks := ExtractBlocks(`<div><p>inner</p></div><p>sibling</p>`)
	if len(blocks) != 2 || !strings.HasPrefix(blocks[0], "<div>") {
		t.Errorf("blocks = %q", blocks)
	}
}

func TestExtractBlocks_BareTextFallsBackToParagraphSplit(t *testing.T) {
	blocks := ExtractBlocks(`just text</p>more text</p>`)
	if len(blocks) == 0 {
		t.Fatal("expected fallback blocks, got none")
	}
}
