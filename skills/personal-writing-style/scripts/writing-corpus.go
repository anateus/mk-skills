// Command writing-corpus extracts text authored by the local user from coding
// transcripts and messaging stores. It emits a private, bounded NDJSON corpus.
package main

import (
	"bufio"
	"bytes"
	"compress/gzip"
	"container/heap"
	"crypto/sha256"
	"encoding/binary"
	"encoding/hex"
	"encoding/json"
	"errors"
	"flag"
	"fmt"
	"html"
	"io"
	"io/fs"
	"os"
	"os/exec"
	"path/filepath"
	"regexp"
	"sort"
	"strconv"
	"strings"
	"time"
	"unicode/utf8"
)

type record struct {
	ID        string `json:"id"`
	Source    string `json:"source"`
	Timestamp string `json:"timestamp"`
	Text      string `json:"text"`
	WordCount int    `json:"word_count"`
}

type sourceStats struct {
	Available             bool   `json:"available"`
	Scanned               int    `json:"scanned"`
	Candidates            int    `json:"candidates"`
	Deduplicated          int    `json:"deduplicated"`
	Emitted               int    `json:"emitted"`
	SkippedAttributedBody int    `json:"skipped_attributed_body,omitempty"`
	Error                 string `json:"error,omitempty"`
}

type scoredRecord struct {
	record
	score uint64
}
type maxHeap []scoredRecord

func (h maxHeap) Len() int           { return len(h) }
func (h maxHeap) Less(i, j int) bool { return h[i].score > h[j].score }
func (h maxHeap) Swap(i, j int)      { h[i], h[j] = h[j], h[i] }
func (h *maxHeap) Push(x any)        { *h = append(*h, x.(scoredRecord)) }
func (h *maxHeap) Pop() any          { old := *h; n := len(old); x := old[n-1]; *h = old[:n-1]; return x }

type bucket struct {
	limit int
	items maxHeap
	seen  map[[32]byte]struct{}
}
type collector struct {
	minChars int
	maxChars int
	limit    int
	buckets  map[string]*bucket
	stats    map[string]*sourceStats
}

func newCollector(minChars, maxChars, limit int) *collector {
	return &collector{minChars: minChars, maxChars: maxChars, limit: limit, buckets: map[string]*bucket{}, stats: map[string]*sourceStats{}}
}
func (c *collector) stat(source string) *sourceStats {
	if c.stats[source] == nil {
		c.stats[source] = &sourceStats{}
	}
	return c.stats[source]
}
func (c *collector) add(source, timestamp, text string) {
	s := c.stat(source)
	s.Scanned++
	text = cleanText(text)
	if text == "" || utf8.RuneCountInString(text) < c.minChars {
		return
	}
	if c.maxChars > 0 && utf8.RuneCountInString(text) > c.maxChars {
		text = string([]rune(text)[:c.maxChars])
	}
	s.Candidates++
	textKey := sha256.Sum256([]byte(text))
	b := c.buckets[source]
	if b == nil {
		b = &bucket{limit: c.limit, seen: map[[32]byte]struct{}{}}
		c.buckets[source] = b
	}
	if _, ok := b.seen[textKey]; ok {
		s.Deduplicated++
		return
	}
	b.seen[textKey] = struct{}{}
	idBytes := sha256.Sum256([]byte(source + "\x00" + timestamp + "\x00" + text))
	item := scoredRecord{record: record{ID: hex.EncodeToString(idBytes[:8]), Source: source, Timestamp: timestamp, Text: text}, score: binary.BigEndian.Uint64(idBytes[:8])}
	item.WordCount = len(strings.Fields(text))
	if b.limit == 0 || len(b.items) < b.limit {
		heap.Push(&b.items, item)
	} else if item.score < b.items[0].score {
		heap.Pop(&b.items)
		heap.Push(&b.items, item)
	}
}

func cleanText(text string) string {
	text = strings.ReplaceAll(strings.ReplaceAll(text, "\r\n", "\n"), "\r", "\n")
	text = strings.ReplaceAll(text, "\x00", "")
	text = removeTagged(text, "<environment_context>", "</environment_context>")
	text = removeTagged(text, "<system-reminder>", "</system-reminder>")
	text = strings.TrimSpace(text)
	for _, prefix := range []string{"# AGENTS.md instructions", "<INSTRUCTIONS>", "<local-command-caveat>", "<command-name>", "<command-message>", "<ide_opened_file>"} {
		if strings.HasPrefix(text, prefix) {
			return ""
		}
	}
	return text
}
func removeTagged(text, open, close string) string {
	for {
		start := strings.Index(text, open)
		if start < 0 {
			return text
		}
		end := strings.Index(text[start+len(open):], close)
		if end < 0 {
			return strings.TrimSpace(text[:start])
		}
		end += start + len(open) + len(close)
		text = text[:start] + text[end:]
	}
}

func scanJSONL(path string, visit func([]byte) error) error {
	f, err := os.Open(path)
	if err != nil {
		return err
	}
	defer f.Close()
	scanner := bufio.NewScanner(f)
	scanner.Buffer(make([]byte, 64*1024), 64*1024*1024)
	for scanner.Scan() {
		if err := visit(append([]byte(nil), scanner.Bytes()...)); err != nil {
			return fmt.Errorf("%s: %w", filepath.Base(path), err)
		}
	}
	return scanner.Err()
}
func walkFiles(root string, visit func(string, fs.DirEntry) error) error {
	info, err := os.Stat(root)
	if err != nil {
		return err
	}
	if !info.IsDir() {
		return errors.New("not a directory")
	}
	return filepath.WalkDir(root, func(path string, entry fs.DirEntry, err error) error {
		if err != nil {
			return err
		}
		return visit(path, entry)
	})
}

func extractClaude(c *collector, root string) error {
	return walkFiles(root, func(path string, entry fs.DirEntry) error {
		if entry.IsDir() && entry.Name() == "subagents" {
			return filepath.SkipDir
		}
		if entry.IsDir() || filepath.Ext(path) != ".jsonl" {
			return nil
		}
		return scanJSONL(path, func(line []byte) error {
			var row struct {
				Type                    string          `json:"type"`
				Timestamp               string          `json:"timestamp"`
				IsSidechain             bool            `json:"isSidechain"`
				AgentID                 json.RawMessage `json:"agentId"`
				SourceToolAssistantUUID json.RawMessage `json:"sourceToolAssistantUUID"`
				Message                 struct {
					Role    string          `json:"role"`
					Content json.RawMessage `json:"content"`
				} `json:"message"`
			}
			if json.Unmarshal(line, &row) != nil || row.Type != "user" || row.Message.Role != "user" || row.IsSidechain || present(row.AgentID) || present(row.SourceToolAssistantUUID) {
				return nil
			}
			var text string
			if json.Unmarshal(row.Message.Content, &text) == nil {
				c.add("claude", row.Timestamp, text)
				return nil
			}
			var blocks []struct {
				Type string `json:"type"`
				Text string `json:"text"`
			}
			if json.Unmarshal(row.Message.Content, &blocks) == nil {
				for _, block := range blocks {
					if block.Type == "text" {
						c.add("claude", row.Timestamp, block.Text)
					}
				}
			}
			return nil
		})
	})
}
func present(raw json.RawMessage) bool {
	return len(raw) > 0 && string(raw) != "null" && string(raw) != `""`
}

func extractCodex(c *collector, root string) error {
	return walkFiles(root, func(path string, entry fs.DirEntry) error {
		if entry.IsDir() || filepath.Ext(path) != ".jsonl" {
			return nil
		}
		return scanJSONL(path, func(line []byte) error {
			var row struct {
				Type      string `json:"type"`
				Timestamp string `json:"timestamp"`
				Payload   struct {
					Type    string `json:"type"`
					Role    string `json:"role"`
					Content []struct {
						Type string `json:"type"`
						Text string `json:"text"`
					} `json:"content"`
				} `json:"payload"`
			}
			if json.Unmarshal(line, &row) != nil || row.Type != "response_item" || row.Payload.Type != "message" || row.Payload.Role != "user" {
				return nil
			}
			for _, block := range row.Payload.Content {
				if block.Type == "input_text" {
					c.add("codex", row.Timestamp, block.Text)
				}
			}
			return nil
		})
	})
}

type sqlRow struct {
	Timestamp string `json:"timestamp"`
	Text      string `json:"text"`
	HTML      bool   `json:"html"`
}

func extractSQLite(c *collector, source, db, query string, clean func(string) string) error {
	if _, err := os.Stat(db); err != nil {
		return err
	}
	cmd := exec.Command("sqlite3", "-readonly", db, query)
	stdout, err := cmd.StdoutPipe()
	if err != nil {
		return err
	}
	var stderr bytes.Buffer
	cmd.Stderr = &stderr
	if err := cmd.Start(); err != nil {
		return err
	}
	scanner := bufio.NewScanner(stdout)
	scanner.Buffer(make([]byte, 64*1024), 64*1024*1024)
	for scanner.Scan() {
		var row sqlRow
		if err := json.Unmarshal(scanner.Bytes(), &row); err != nil {
			_ = cmd.Process.Kill()
			return err
		}
		if clean != nil {
			if row.HTML {
				row.Text = cleanHTML(row.Text)
			} else {
				row.Text = clean(row.Text)
			}
		}
		c.add(source, row.Timestamp, row.Text)
	}
	if err := scanner.Err(); err != nil {
		_ = cmd.Process.Kill()
		return err
	}
	if err := cmd.Wait(); err != nil {
		return fmt.Errorf("sqlite3: %s", strings.TrimSpace(stderr.String()))
	}
	return nil
}

var emailQuote = regexp.MustCompile(`(?i)^(on .{1,200}wrote:|from:\s|sent:\s|to:\s|subject:\s|-----original message-----|_{5,})`)
var htmlQuote = regexp.MustCompile(`(?is)<blockquote\b.*`)
var htmlDrop = regexp.MustCompile(`(?is)<(style|script)\b[^>]*>.*?</(style|script)>`)
var htmlBreak = regexp.MustCompile(`(?i)(?:</?(?:p|div|li|tr|h[1-6])\b[^>]*>|<br\b[^>]*>)`)
var htmlTag = regexp.MustCompile(`(?s)<[^>]+>`)

func cleanEmail(text string) string {
	lines := strings.Split(strings.ReplaceAll(text, "\r\n", "\n"), "\n")
	kept := make([]string, 0, len(lines))
	for _, line := range lines {
		if strings.HasPrefix(strings.TrimSpace(line), ">") || emailQuote.MatchString(strings.TrimSpace(line)) {
			break
		}
		kept = append(kept, line)
	}
	return strings.TrimSpace(strings.Join(kept, "\n"))
}

func cleanHTML(text string) string {
	text = htmlQuote.ReplaceAllString(text, "")
	text = htmlDrop.ReplaceAllString(text, "")
	text = htmlBreak.ReplaceAllString(text, "\n")
	text = html.UnescapeString(htmlTag.ReplaceAllString(text, ""))
	lines := strings.Split(text, "\n")
	cleaned := make([]string, 0, len(lines))
	for _, line := range lines {
		line = strings.Join(strings.Fields(line), " ")
		if line != "" || (len(cleaned) > 0 && cleaned[len(cleaned)-1] != "") {
			cleaned = append(cleaned, line)
		}
	}
	return cleanEmail(strings.Join(cleaned, "\n"))
}

func extractSlack(c *collector, root, userID string) error {
	if userID == "" {
		return errors.New("--slack-user-id is required with --slack-export")
	}
	return walkFiles(root, func(path string, entry fs.DirEntry) error {
		if entry.IsDir() || filepath.Ext(path) != ".json" {
			return nil
		}
		base := filepath.Base(path)
		if base == "users.json" || base == "channels.json" || base == "integration_logs.json" {
			return nil
		}
		f, err := os.Open(path)
		if err != nil {
			return err
		}
		defer f.Close()
		dec := json.NewDecoder(f)
		tok, err := dec.Token()
		if err == io.EOF {
			return nil
		}
		if err != nil || tok != json.Delim('[') {
			return nil
		}
		for dec.More() {
			var msg struct {
				Type string `json:"type"`
				User string `json:"user"`
				TS   string `json:"ts"`
				Text string `json:"text"`
			}
			if err := dec.Decode(&msg); err != nil {
				return err
			}
			if msg.Type == "message" && msg.User == userID {
				c.add("slack", slackTimestamp(msg.TS), msg.Text)
			}
		}
		return nil
	})
}
func slackTimestamp(ts string) string {
	parts := strings.SplitN(ts, ".", 2)
	seconds, err := strconv.ParseInt(parts[0], 10, 64)
	if err != nil {
		return ""
	}
	return time.Unix(seconds, 0).UTC().Format(time.RFC3339)
}

func (c *collector) records() []record {
	var result []record
	for _, source := range []string{"claude", "codex", "imessage", "mimestream", "slack"} {
		if b := c.buckets[source]; b != nil {
			items := append([]scoredRecord(nil), b.items...)
			sort.Slice(items, func(i, j int) bool {
				if items[i].Timestamp == items[j].Timestamp {
					return items[i].ID < items[j].ID
				}
				return items[i].Timestamp < items[j].Timestamp
			})
			for _, item := range items {
				result = append(result, item.record)
			}
			c.stat(source).Emitted = len(items)
		}
	}
	return result
}
func markResult(c *collector, source string, err error) {
	s := c.stat(source)
	if err == nil {
		s.Available = true
		return
	}
	if errors.Is(err, os.ErrNotExist) {
		s.Error = "not found"
	} else {
		s.Error = err.Error()
	}
}

func main() {
	home, _ := os.UserHomeDir()
	var output, sources, claudeDir, codexDir, imessageDB, mimestreamDB, slackExport, slackUserID string
	var maxPerSource, minChars, maxChars int
	var dryRun bool
	flag.StringVar(&output, "output", "", "private gzip-compressed NDJSON output path (required unless --dry-run)")
	flag.StringVar(&sources, "sources", "claude,codex,imessage,mimestream", "comma-separated sources")
	flag.IntVar(&maxPerSource, "max-per-source", 5000, "deterministic sample size per source; 0 keeps all")
	flag.IntVar(&minChars, "min-chars", 8, "discard shorter messages")
	flag.IntVar(&maxChars, "max-chars", 12000, "truncate longer messages; 0 disables")
	flag.BoolVar(&dryRun, "dry-run", false, "scan and report counts without writing text")
	flag.StringVar(&claudeDir, "claude-dir", filepath.Join(home, ".claude", "projects"), "Claude transcript root")
	flag.StringVar(&codexDir, "codex-dir", filepath.Join(home, ".codex", "sessions"), "Codex transcript root")
	flag.StringVar(&imessageDB, "imessage-db", filepath.Join(home, "Library", "Messages", "chat.db"), "iMessage chat.db")
	flag.StringVar(&mimestreamDB, "mimestream-db", filepath.Join(home, "Library", "Containers", "com.mimestream.Mimestream", "Data", "Library", "Application Support", "Mimestream", "Mimestream.sqlite"), "Mimestream database")
	flag.StringVar(&slackExport, "slack-export", "", "Slack standard export directory")
	flag.StringVar(&slackUserID, "slack-user-id", "", "author user ID in Slack export")
	flag.Parse()
	if maxPerSource < 0 || minChars < 0 || maxChars < 0 || (!dryRun && output == "") {
		fmt.Fprintln(os.Stderr, "invalid arguments: --output is required and numeric limits must be non-negative")
		os.Exit(2)
	}
	set := map[string]bool{}
	for _, source := range strings.Split(sources, ",") {
		set[strings.TrimSpace(source)] = true
	}
	if slackExport != "" {
		set["slack"] = true
	}
	c := newCollector(minChars, maxChars, maxPerSource)
	if set["claude"] {
		markResult(c, "claude", extractClaude(c, claudeDir))
	}
	if set["codex"] {
		markResult(c, "codex", extractCodex(c, codexDir))
	}
	if set["imessage"] {
		query := `select json_object('timestamp', strftime('%Y-%m-%dT%H:%M:%SZ', (case when date > 1000000000000 then date/1000000000 else date end) + 978307200, 'unixepoch'), 'text', text) from message where is_from_me=1 and item_type=0 and associated_message_type=0 and text is not null;`
		markResult(c, "imessage", extractSQLite(c, "imessage", imessageDB, query, nil))
		if c.stat("imessage").Available {
			countQuery := `select count(*) from message where is_from_me=1 and item_type=0 and associated_message_type=0 and text is null and attributedBody is not null;`
			if out, err := exec.Command("sqlite3", "-readonly", imessageDB, countQuery).Output(); err == nil {
				c.stat("imessage").SkippedAttributedBody, _ = strconv.Atoi(strings.TrimSpace(string(out)))
			}
		}
	}
	if set["mimestream"] {
		query := `select json_object('timestamp', strftime('%Y-%m-%dT%H:%M:%SZ', m.ZDATESENT + 978307200, 'unixepoch'), 'text', coalesce(c.ZBODYTEXT, c.ZBODYHTML), 'html', case when c.ZBODYTEXT is null then json('true') else json('false') end) from ZMESSAGE m join ZMESSAGECONTENT c on c.ZMESSAGE=m.Z_PK where m.ZISSENT=1 and coalesce(c.ZBODYTEXT, c.ZBODYHTML) is not null;`
		markResult(c, "mimestream", extractSQLite(c, "mimestream", mimestreamDB, query, cleanEmail))
	}
	if set["slack"] {
		markResult(c, "slack", extractSlack(c, slackExport, slackUserID))
	}
	records := c.records()
	if !dryRun {
		if err := os.MkdirAll(filepath.Dir(output), 0o700); err != nil {
			fmt.Fprintln(os.Stderr, err)
			os.Exit(1)
		}
		f, err := os.OpenFile(output, os.O_WRONLY|os.O_CREATE|os.O_TRUNC, 0o600)
		if err != nil {
			fmt.Fprintln(os.Stderr, err)
			os.Exit(1)
		}
		_ = f.Chmod(0o600)
		compressed, err := gzip.NewWriterLevel(f, gzip.BestSpeed)
		if err != nil {
			_ = f.Close()
			fmt.Fprintln(os.Stderr, err)
			os.Exit(1)
		}
		enc := json.NewEncoder(compressed)
		for _, row := range records {
			if err := enc.Encode(row); err != nil {
				_ = compressed.Close()
				_ = f.Close()
				fmt.Fprintln(os.Stderr, err)
				os.Exit(1)
			}
		}
		if err := compressed.Close(); err != nil {
			_ = f.Close()
			fmt.Fprintln(os.Stderr, err)
			os.Exit(1)
		}
		if err := f.Close(); err != nil {
			fmt.Fprintln(os.Stderr, err)
			os.Exit(1)
		}
	}
	stats, _ := json.Marshal(c.stats)
	fmt.Fprintln(os.Stderr, string(stats))
}
