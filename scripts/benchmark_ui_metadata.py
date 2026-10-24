"""Compare extension catalog rebuilds and warm display reads in one process."""
import argparse
import json
import logging
from pathlib import Path
import statistics
import sys
import time


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--samples', type=int, default=5)
    args = parser.parse_args()
    if not 1 <= args.samples <= 100:
        parser.error('--samples must be between 1 and 100')
    logging.disable(logging.WARNING)
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'app'))
    import agent_extensions as extensions

    # Imports and runtime initialization are excluded from the comparison.
    snapshot = extensions.extensions_snapshot()
    def measure(call):
        samples = []
        for _ in range(args.samples):
            started = time.perf_counter()
            call()
            samples.append((time.perf_counter() - started) * 1000)
        return {'median_ms': round(statistics.median(samples), 3), 'max_ms': round(max(samples), 3)}

    rebuilt = measure(extensions._build_extensions_snapshot)
    cached = measure(extensions.extensions_snapshot)
    print(json.dumps({'samples': args.samples, 'plugins': len(snapshot['plugins']),
                      'rebuild': rebuilt, 'cached': cached,
                      'median_speedup': round(rebuilt['median_ms'] / max(cached['median_ms'], 0.001), 1)}, indent=2))


if __name__ == '__main__':
    main()
