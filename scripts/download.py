import argparse
import subprocess
import sys

from papercli.cli import download


def get_pending_venues(year: int | None = None) -> list[str]:
    import sqlite3
    from papercli.db import DEFAULT_DB

    if not DEFAULT_DB.exists():
        return []
    conn = sqlite3.connect(DEFAULT_DB)
    sql = "SELECT DISTINCT venue FROM papers WHERE pdf_path IS NULL AND pdf_url != ''"
    args = []
    if year:
        sql += " AND year = ?"
        args.append(year)
    cursor = conn.cursor()
    rows = cursor.execute(sql, args).fetchall()
    conn.close()
    return [r[0] for r in rows]


def main() -> None:
    parser = argparse.ArgumentParser(description="Download pending PDFs.")
    parser.add_argument(
        "--venue",
        default=None,
        help="Limit to a specific venue or comma-separated list of venues",
    )
    parser.add_argument("--year", default=None, help="Limit to a specific year")
    parser.add_argument(
        "--delay",
        type=float,
        default=0.5,
        help="Delay between requests in seconds",
    )
    parser.add_argument(
        "--parallel",
        action="store_true",
        help="Download multiple venues in parallel",
    )
    args = parser.parse_args()

    year = int(args.year) if args.year else None

    if args.parallel:
        if args.venue:
            venues = [v.strip() for v in args.venue.split(",") if v.strip()]
        else:
            venues = get_pending_venues(year)

        if not venues:
            print("No pending PDFs or venues to download.")
            return

        print(f"Starting parallel downloads for: {', '.join(venues)}...")
        processes = []
        for venue in venues:
            cmd = ["uv", "run", "python", "scripts/download.py", "--venue", venue]
            if args.year:
                cmd += ["--year", args.year]
            if args.delay != 0.5:
                cmd += ["--delay", str(args.delay)]
            proc = subprocess.Popen(cmd)
            processes.append((venue, proc))

        failed = []
        for venue, proc in processes:
            exit_code = proc.wait()
            if exit_code != 0:
                print(
                    f"[-] Download process for {venue} failed with exit code {exit_code}",
                    file=sys.stderr,
                )
                failed.append(venue)
            else:
                print(f"[+] Download process for {venue} completed successfully.")

        if failed:
            sys.exit(1)
    else:
        venue = args.venue if args.venue else None
        download(venue=venue, year=year, delay=args.delay)


if __name__ == "__main__":
    main()
