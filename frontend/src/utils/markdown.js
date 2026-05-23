import { marked } from 'marked';
import MarkdownIt from 'markdown-it';
import DOMPurify from 'dompurify';
import mermaid from 'mermaid';

let mermaidReady = false;
function ensureMermaid() {
  if (mermaidReady) return;
  try {
    mermaid.initialize({ startOnLoad: false, theme: 'dark', securityLevel: 'loose' });
    mermaidReady = true;
  } catch (err) {
    console.warn('mermaid init failed', err);
  }
}

const md = new MarkdownIt({ html: false, linkify: true, breaks: false });

marked.setOptions({ breaks: true, gfm: true });

export function renderMarkdown(source, { useMarkdownIt = false } = {}) {
  if (!source) return '';
  const html = useMarkdownIt ? md.render(source) : marked.parse(source);
  return DOMPurify.sanitize(html);
}

export async function renderMermaid(rootEl) {
  if (!rootEl) return;
  ensureMermaid();
  const blocks = rootEl.querySelectorAll('pre > code.language-mermaid, code.language-mermaid');
  if (!blocks.length) return;
  let counter = 0;
  for (const codeEl of blocks) {
    const pre = codeEl.parentElement;
    const host = pre && pre.tagName === 'PRE' ? pre : codeEl;
    const id = `mermaid-${Date.now()}-${counter++}`;
    const def = codeEl.textContent || '';
    try {
      const { svg } = await mermaid.render(id, def);
      const wrap = document.createElement('div');
      wrap.className = 'mermaid-render';
      wrap.innerHTML = svg;
      host.replaceWith(wrap);
    } catch (err) {
      const errEl = document.createElement('div');
      errEl.className = 'mermaid-error';
      errEl.textContent = `Mermaid 渲染失败：${err.message || err}`;
      host.replaceWith(errEl);
    }
  }
}
