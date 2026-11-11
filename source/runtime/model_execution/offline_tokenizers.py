"""Prepare verified local tokenizer data before LiteLLM can request public assets."""

import hashlib
import json
import logging
import os
from pathlib import Path
from tempfile import NamedTemporaryFile


ASSET_DIRECTORY = Path(__file__).with_name('tokenizer_assets')
DEFAULT_CACHE = Path(__file__).resolve().parents[3] / 'work/cache/tokenizers'
logger = logging.getLogger(__name__)


class OfflineTokenizerError(ValueError):
    """Tokenizer setup must be repaired before any model request is attempted."""


def _verified_assets(directory):
    """Read and validate all bundled data before making cache changes."""
    manifest = json.loads((directory / 'manifest.json').read_text(encoding='utf-8'))
    encodings = [item['encoding'] for item in manifest['assets']]
    if manifest['schema_version'] != 1 or sorted(encodings) != ['cl100k_base', 'o200k_base']:
        raise ValueError('Unsupported or empty tokenizer manifest')
    assets = []
    for item in manifest['assets']:
        path = directory / item['file']
        if path.parent != directory or path.name != item['encoding'] + '.tiktoken':
            raise ValueError('Invalid tokenizer asset path')
        data = path.read_bytes()
        if hashlib.sha256(data).hexdigest() != item['sha256']:
            raise ValueError('Bundled tokenizer checksum mismatch: ' + path.name)
        assets.append((item, data))
    return assets


def _cache_directory():
    """Honor explicit cache locations, including LiteLLM's overriding variable."""
    custom = os.environ.get('CUSTOM_TIKTOKEN_CACHE_DIR')
    standard = os.environ.get('TIKTOKEN_CACHE_DIR')
    if custom is not None and standard is not None and Path(custom).resolve() != Path(standard).resolve():
        raise ValueError('CUSTOM_TIKTOKEN_CACHE_DIR and TIKTOKEN_CACHE_DIR must select the same directory')
    selected = custom if custom is not None else standard
    if selected is None:
        selected = os.environ.get('DATA_GYM_CACHE_DIR', str(DEFAULT_CACHE))
    if not selected.strip():
        raise ValueError('An empty tokenizer cache disables caching; select a writable local directory')
    return Path(selected).expanduser().resolve()


def _populate_cache(cache, assets):
    """Atomically install missing or damaged cache entries from verified bundled data."""
    cache.mkdir(parents=True, exist_ok=True)
    for item, data in assets:
        # Tiktoken names entries by the SHA-1 of their original URL, not the data filename.
        destination = cache / hashlib.sha1(item['url'].encode('utf-8')).hexdigest()
        if destination.is_file() and hashlib.sha256(destination.read_bytes()).hexdigest() == item['sha256']:
            continue
        temporary = None
        try:
            with NamedTemporaryFile(dir=cache, delete=False) as stream:
                temporary = Path(stream.name)
                stream.write(data)
            temporary.replace(destination)
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)


def _read_local_tokenizer_file(path):
    """Permit local tokenizer reads; a cache miss must never start a public download."""
    if '://' in path:
        raise OfflineTokenizerError('Tokenizer data is not available locally: ' + path +
            '. Restore the bundled tokenizer assets or provision the matching cache entry; public downloads are disabled.')
    return Path(path).read_bytes()


def prepare_offline_tokenizers():
    """Verify assets, populate a persistent cache and initialize encodings without HTTP.

    Set both cache variables before LiteLLM imports, since some versions replace the
    standard variable. Only tiktoken data fetching is restricted; model traffic is untouched.
    Raise OfflineTokenizerError for setup failures, outside the model retry loop.
    """
    try:
        assets = _verified_assets(ASSET_DIRECTORY)
        cache = _cache_directory()
        _populate_cache(cache, assets)
        os.environ['TIKTOKEN_CACHE_DIR'] = str(cache)
        os.environ['CUSTOM_TIKTOKEN_CACHE_DIR'] = str(cache)
        import tiktoken
        import tiktoken.load

        # A later unsupported encoding or cache corruption must fail rather than fetch.
        tiktoken.load.read_file = _read_local_tokenizer_file
        for item, _ in assets:
            tiktoken.get_encoding(item['encoding'])
    except (OSError, ValueError, KeyError, TypeError, ImportError) as error:
        raise OfflineTokenizerError('Offline tokenizer setup failed: ' + str(error) +
            '. Restore source/runtime/model_execution/tokenizer_assets from the repository and check cache permissions and dependency versions.') from error
    logger.info('Offline tokenizer cache ready: %s (%s)', cache,
                ', '.join(item['encoding'] for item, _ in assets))
    return cache
