import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from backend.ai_service.prepare_legal import prepare, split_page


class PrepareLegalTests(unittest.TestCase):
    def test_split_preserves_coverage_and_limits(self):
        text = 'word ' * 2000
        chunks = list(split_page(text))
        self.assertTrue(all(0 < len(c) <= 2400 for c in chunks))
        self.assertGreater(sum(map(len, chunks)), len(text))
        self.assertEqual(list(split_page('short')), ['short'])

    def test_manifest_import_is_repeatable_and_rejects_changed_pdf(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            pdf = b'%PDF-test fixture'
            digest = hashlib.sha256(pdf).hexdigest()
            (root / 'source.pdf').write_bytes(pdf)
            page = dict(source_id='test', language='en', page=1, raw_sha256=digest,
                        text='Synthetic legal text.')
            (root / 'pages.jsonl').write_text(json.dumps(page))
            source = dict(source_id='test', language='en', title='Test', canonical_url='fixture:test',
                          source_kind='judgment', approval_status='unreviewed',
                          acquisition_status='downloaded_pdf_text_extracted',
                          local_path='source.pdf', extracted_path='pages.jsonl', sha256=digest, page_count=1)
            manifest = root / 'manifest.json'
            manifest.write_text(json.dumps(dict(schema_version=1, sources=[source,
                dict(source_id='missing', acquisition_status='not_acquired')])))
            chunks, skipped = prepare(manifest)
            self.assertEqual((chunks, skipped), prepare(manifest))
            self.assertEqual(skipped, ['missing'])
            self.assertEqual(chunks[0].provenance.page, 1)
            self.assertFalse(chunks[0].provenance.runtime_enabled)
            (root / 'source.pdf').write_bytes(b'%PDF-changed')
            with self.assertRaisesRegex(ValueError, 'hash mismatch'):
                prepare(manifest)


if __name__ == '__main__':
    unittest.main()
