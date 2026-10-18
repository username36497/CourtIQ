"""Validated, transactional, idempotent snapshot ingestion of locally approved guides."""
import argparse
import hashlib
import json
import os
import re
from pathlib import Path
from sqlalchemy import delete
from .db import Chunk, Run, Session, init_db

DEFAULT_GUIDES = Path(os.getenv('GUIDE_DIR', str(Path(__file__).resolve().parents[2] / 'data' / 'guides')))

def ingest(directory=DEFAULT_GUIDES):
    files = sorted(Path(directory).glob('*.json'))
    if not files: raise ValueError('No guide JSON files found; existing index was preserved.')
    chunks, sources = [], set()
    for file in files:
        doc = json.loads(file.read_text())
        for key in ('source', 'title', 'edition', 'patch', 'url', 'sample', 'text'):
            if key not in doc: raise ValueError(f'{file.name}: missing {key}')
        if not all(isinstance(doc[k], str) and doc[k].strip() for k in ('source','title','edition','patch','text')):
            raise ValueError(f'{file.name}: metadata and text must be nonempty strings')
        if type(doc['sample']) is not bool: raise ValueError('sample must be a JSON boolean')
        if doc['source'] in sources: raise ValueError('Duplicate source identifier')
        if doc['edition'] != '2K27': raise ValueError('Only 2K27 guides are allowed in this index')
        if not isinstance(doc['url'], str) or (doc['url'] and not doc['url'].startswith('https://')):
            raise ValueError('Source URL must be HTTPS or empty for local notes')
        if len(doc['text']) > 100_000: raise ValueError('Guide exceeds 100,000 characters')
        sources.add(doc['source'])
        text = re.sub(r'\s+', ' ', doc['text']).strip()
        words = text.split()
        for start in range(0, len(words), 160):
            part = ' '.join(words[start:start+200])
            identifier = hashlib.sha256(f"{doc['source']}:{doc['patch']}:{start}:{part}".encode()).hexdigest()
            chunks.append(Chunk(id=identifier, **{k: doc[k] for k in ('source','title','edition','patch','url','sample')}, text=part))
    # Validate every file before touching the old snapshot; commit everything together.
    with Session.begin() as db:
        db.execute(delete(Chunk))
        db.add_all(chunks)
        summary = {'documents': len(files), 'chunks': len(chunks), 'sample_documents': sum(json.loads(f.read_text())['sample'] for f in files)}
        db.add(Run(summary=summary))
    return summary

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--directory', type=Path, default=DEFAULT_GUIDES)
    args = parser.parse_args()
    init_db()
    print(json.dumps(ingest(args.directory), indent=2))
