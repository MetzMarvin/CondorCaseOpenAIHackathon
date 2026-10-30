"""Prepare downloaded legal pages for research retrieval without network access."""
import argparse
import hashlib
import json
from pathlib import Path

from .rag import KnowledgeChunk, LegalProvenance
from .settings import ROOT


def local_file(root, relative):
    path = (root / relative).resolve()
    if not path.is_relative_to(root.resolve()):
        raise ValueError('Manifest path escapes the corpus directory')
    return path


def split_page(text, size=2400, overlap=300):
    """Bounded passages with overlap; retain original text and physical page boundaries."""
    start = 0
    while start < len(text):
        end = min(start + size, len(text))
        if end < len(text):
            boundary = text.rfind(' ', start + size // 2, end)
            if boundary != -1:
                end = boundary
        passage = text[start:end].strip()
        if passage:
            yield passage
        if end == len(text):
            break
        start = end - overlap


def prepare(manifest_path):
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    if manifest['schema_version'] != 1:
        raise ValueError('Unsupported manifest schema')
    chunks, skipped = [], []
    seen = set()
    for source in manifest['sources']:
        source_id = source['source_id']
        if source_id in seen:
            raise ValueError(f'Duplicate source: {source_id}')
        seen.add(source_id)
        if source['acquisition_status'] != 'downloaded_pdf_text_extracted':
            skipped.append(source_id)
            continue
        if source['language'] != 'en':
            raise ValueError(f'{source_id}: default BM25 requires English corpus')
        pdf = local_file(manifest_path.parent, source['local_path']).read_bytes()
        digest = hashlib.sha256(pdf).hexdigest()
        if not pdf.startswith(b'%PDF-') or digest != source['sha256']:
            raise ValueError(f'{source_id}: PDF signature/hash mismatch')
        extracted = local_file(manifest_path.parent, source['extracted_path']).read_bytes()
        pages = [json.loads(line) for line in extracted.decode('utf-8').splitlines() if line.strip()]
        if [p['page'] for p in pages] != list(range(1, source['page_count'] + 1)):
            raise ValueError(f'{source_id}: missing, duplicate or unordered pages')
        # Include extraction bytes and splitter version so changed text has distinct IDs.
        version = 'pages-v1-' + hashlib.sha256(pdf + extracted).hexdigest()
        for page in pages:
            if (page['source_id'] != source_id or page['language'] != 'en'
                    or page['raw_sha256'] != digest or not page['text'].strip()):
                raise ValueError(f'{source_id}: invalid page provenance/text')
            for index, text in enumerate(split_page(page['text']), 1):
                chunks.append(KnowledgeChunk(
                    source_id=source_id, version=version,
                    chunk_id=f"page-{page['page']:03d}-part-{index:03d}",
                    title=source['title'], source_uri=source['canonical_url'],
                    kind='legal', text=text,
                    provenance=LegalProvenance(
                        page=page['page'], pdf_sha256=digest,
                        source_kind=source['source_kind'], language=source['language'],
                        approval_status=source['approval_status'], runtime_enabled=False),
                ))
    if not chunks:
        raise ValueError('No acquired sources found')
    return chunks, skipped


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', type=Path, default=ROOT / 'data/legal/source-manifest.json')
    parser.add_argument('--output', type=Path, default=ROOT / 'data/processed/legal-research.jsonl')
    args = parser.parse_args()
    chunks, skipped = prepare(args.manifest)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(''.join(c.model_dump_json() + '\n' for c in chunks), encoding='utf-8')
    print(json.dumps({'output': str(args.output), 'sources': len({c.source_id for c in chunks}),
                      'chunks': len(chunks), 'skipped_unacquired': skipped}))


if __name__ == '__main__':
    main()
