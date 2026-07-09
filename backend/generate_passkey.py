"""
Generate passkeys for the 3DPharma app.

Usage:
  python generate_passkey.py                        # 1 lifetime key
  python generate_passkey.py --hours 2              # 1 key valid 2h from first use
  python generate_passkey.py --hours 24 --count 10  # 10 keys valid 24h
  python generate_passkey.py --hours 2 --count 500  # 500 keys valid 2h
  python generate_passkey.py --count 500            # 500 lifetime keys
"""

import argparse
import random
import string

_B62 = string.ascii_uppercase + string.ascii_lowercase + string.digits  # 62 chars


def _b62_encode(data: bytes) -> str:
    n = int.from_bytes(data, "big")
    if n == 0:
        return _B62[0]
    result = []
    while n:
        result.append(_B62[n % 62])
        n //= 62
    return "".join(reversed(result))


def _encode(raw: str) -> str:
    return _b62_encode(raw.encode())


def generate_passkey(duration_hours: float | None = None) -> str:
    """
    Create a short passkey (~12 chars).
    duration_hours=None  → lifetime
    duration_hours=2     → valid 2 hours from first use
    """
    rand_id = "".join(random.choices(string.ascii_letters + string.digits, k=8))
    duration_tag = "L" if duration_hours is None else str(int(duration_hours))
    raw = f"{rand_id}|{duration_tag}"
    return _encode(raw)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate 3DPharma passkeys.")
    parser.add_argument("--hours", type=float, default=None,
                        help="Validity in hours from first use. Omit for lifetime.")
    parser.add_argument("--count", type=int, default=1,
                        help="Number of passkeys to generate (default: 1).")
    args = parser.parse_args()

    label = f"{args.hours}h from first use" if args.hours else "lifetime"
    print(f"\nGenerating {args.count} passkey(s) [{label}]:\n")

    for i in range(args.count):
        print(generate_passkey(duration_hours=args.hours))
