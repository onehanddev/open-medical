import assert from 'node:assert/strict';
import { test } from 'node:test';
import { createElement } from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import ReactMarkdown from 'react-markdown';
import { findExcerptRange, highlightExcerpt } from '../src/components/ask/highlightExcerpt.ts';
const render = (page, excerpt) => renderToStaticMarkup(createElement(ReactMarkdown,
  { rehypePlugins: [highlightExcerpt(page, excerpt)] }, page));
test('maps whitespace differences to original offsets', () => {
  const excerpt = 'This is the cited passage with enough words to exceed the old anchor minimum.';
  const chunk = excerpt.replaceAll(' ', '  ');
  const before = 'Before\n\n\n\nUnrelated text.\n\n';
  const after = '\n\nAfter stays visible.';
  const page = before + chunk + after;
  const range = findExcerptRange(page, excerpt);
  assert.equal(page.slice(range.start, range.end), chunk);
  assert.equal(page.slice(0, range.start), before);
  assert.equal(page.slice(range.end), after);
});
test('requires the complete chunk rather than a repeated prefix', () => {
  const page = 'The same starting words belong here.\n\nThe same starting words belong elsewhere.';
  const range = findExcerptRange(page, 'The same starting words belong elsewhere.');
  assert.equal(range.start, page.lastIndexOf('The same'));
  assert.equal(findExcerptRange(page, 'The same starting words belong nowhere.'), null);
  assert.equal(findExcerptRange(page, '   '), null);
});
test('preserves full Markdown structure and trailing content', () => {
  const page = 'Before **some cited words** and [a link](https://example.com) after.\n\nLast paragraph.';
  const html = render(page, 'cited words** and [a link](https://example.com)');
  assert.equal(html.replace(/<mark[^>]*>|<\/mark>/g, ''), render(page, ''));
  assert.match(html, /<mark class="source-match">cited words<\/mark>/);
  assert.ok(!html.includes('source-match">some'));
  assert.ok(html.endsWith('<p>Last paragraph.</p>'));
});
test('handles escapes and entities before partial highlights', () => {
  const page = 'Before &amp; \\* text highlighted after.';
  const html = render(page, 'highlighted');
  assert.match(html, /<mark class="source-match">highlighted<\/mark> after/);
  assert.equal(html.replace(/<mark[^>]*>|<\/mark>/g, ''), render(page, ''));
});
