#!/usr/bin/env python3
import sys
import argparse
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

from src.utils import setup_logger
from src.config import load_config
from src.runner import JobBotRunner
from src.database import JobDatabase
from src.discord_notifier import DiscordNotifier

console = Console()


def print_banner():
    banner = """[bold cyan]
  ██╗     ██╗███╗   ██╗██╗  ██╗███████╗██████╗ ██╗███╗   ██╗    ██████╗  ██████╗ ████████╗
  ██║     ██║████╗  ██║██║ ██╔╝██╔════╝██╔══██╗██║████╗  ██║    ██╔══██╗██╔═══██╗╚══██╔══╝
  ██║     ██║██╔██╗ ██║█████╔╝ █████╗  ██║  ██║██║██╔██╗ ██║    ██████╔╝██║   ██║   ██║   
  ██║     ██║██║╚██╗██║██╔═██╗ ██╔══╝  ██║  ██║██║██║╚██╗██║    ██╔══██╗██║   ██║   ██║   
  ███████╗██║██║ ╚████║██║  ██╗███████╗██████╔╝██║██║ ╚████║    ██████╔╝╚██████╔╝   ██║   
  ╚══════╝╚═╝╚═╝  ╚═══╝╚═╝  ╚═╝╚══════╝╚═════╝ ╚═╝╚═╝  ╚═══╝    ╚═════╝  ╚═════╝    ╚═╝   
    [/bold cyan]
    [italic yellow]Automated LinkedIn Job Scraper & Discord Alert Bot[/italic yellow]
    """
    console.print(banner)


def cmd_run(args, config):
    """Run bot in continuous daemon mode."""
    print_banner()
    runner = JobBotRunner(config)
    runner.start_daemon()


def cmd_scan_once(args, config):
    """Execute a single scan cycle and exit."""
    print_banner()
    console.print("[bold yellow]Running single scan cycle across all active search profiles...[/bold yellow]\n")
    runner = JobBotRunner(config)
    result = runner.run_all_searches()
    console.print(f"\n[bold green]Scan finished![/bold green] Found: {result['found']}, New: {result['new']}, Alerts Sent: {result['notified']}")


def cmd_test_webhook(args, config):
    """Send a test embed to verify Discord webhook."""
    print_banner()
    webhook_url = args.url or config.settings.discord_webhook_url
    if not webhook_url or "YOUR_WEBHOOK" in webhook_url:
        console.print("[bold red]Error:[/bold red] No valid Discord Webhook URL found in config.yaml or .env!")
        console.print("Please set [cyan]DISCORD_WEBHOOK_URL[/cyan] in your .env or [cyan]discord_webhook_url[/cyan] in config.yaml.")
        sys.exit(1)

    console.print(f"Sending test notification to Discord Webhook: [cyan]{webhook_url[:45]}...[/cyan]")
    notifier = DiscordNotifier(webhook_url)
    success = notifier.send_test_message()
    if success:
        console.print("[bold green]Success![/bold green] Check your Discord channel for the test embed. 🎉")
    else:
        console.print("[bold red]Failed to deliver test message.[/bold red] Please check that the webhook URL is correct.")


def cmd_stats(args, config):
    """Display bot database statistics and recent alerts."""
    print_banner()
    db = JobDatabase(config.settings.database_path)
    stats = db.get_stats()

    table = Table(title="📊 Bot Database Statistics", border_style="cyan")
    table.add_column("Metric", style="bold yellow")
    table.add_column("Value", style="green")

    table.add_row("Total Jobs Discovered", str(stats["total_seen"]))
    table.add_row("Total Discord Alerts Sent", str(stats["total_notified"]))
    table.add_row("Total Scans Executed", str(stats["total_scans"]))
    table.add_row("Last Scan Timestamp", str(stats["last_scan"]))
    table.add_row("Database File", config.settings.database_path)

    console.print(table)
    console.print()

    recent = stats.get("recent_jobs", [])
    if recent:
        rec_table = Table(title="🔔 5 Most Recently Notified Jobs", border_style="blue")
        rec_table.add_column("Title", style="bold white")
        rec_table.add_column("Company", style="cyan")
        rec_table.add_column("Location", style="yellow")
        rec_table.add_column("Filter Profile", style="magenta")
        rec_table.add_column("Notified At", style="dim")

        for job in recent:
            rec_table.add_row(
                job["title"][:35],
                job["company"][:25],
                job["location"][:25],
                job["search_name"][:20],
                job["notified_at"][:19] if job["notified_at"] else "N/A"
            )
        console.print(rec_table)
    else:
        console.print("[dim]No jobs have been notified yet.[/dim]")


def cmd_reset_db(args, config):
    """Clear database history."""
    print_banner()
    if not args.yes:
        confirm = input("⚠️ Are you sure you want to delete all job history from the database? (y/N): ")
        if confirm.lower() != "y":
            console.print("Operation cancelled.")
            return

    db = JobDatabase(config.settings.database_path)
    db.clear_all()
    console.print("[bold green]Database has been reset successfully.[/bold green]")


def cmd_validate(args, config):
    """Validate configuration file and print active search profiles."""
    print_banner()
    console.print("[bold green]Configuration is valid![/bold green]\n")

    settings_table = Table(title="⚙️ Global Settings", border_style="cyan")
    settings_table.add_column("Setting", style="bold yellow")
    settings_table.add_column("Value", style="white")

    wh = config.settings.discord_webhook_url or ""
    masked_wh = f"{wh[:35]}..." if len(wh) > 35 else (wh or "[red]Not configured[/red]")
    settings_table.add_row("Discord Webhook", masked_wh)
    settings_table.add_row("Check Interval", f"{config.settings.check_interval_minutes} minutes")
    settings_table.add_row("Request Delay", f"{config.settings.request_delay_seconds} seconds")
    settings_table.add_row("Fetch Details", str(config.settings.fetch_job_details))
    settings_table.add_row("Database Path", config.settings.database_path)
    console.print(settings_table)
    console.print()

    profiles_table = Table(title="🎯 Configured Search Profiles", border_style="magenta")
    profiles_table.add_column("Name", style="bold white")
    profiles_table.add_column("Keywords", style="cyan")
    profiles_table.add_column("Location", style="yellow")
    profiles_table.add_column("Date Filter", style="green")
    profiles_table.add_column("Status", style="bold")
    profiles_table.add_column("Exclude Keywords", style="red")

    for s in config.searches:
        status = "[green]ENABLED[/green]" if s.enabled else "[dim red]DISABLED[/dim red]"
        excludes = ", ".join(s.filters.title_must_exclude[:3]) if s.filters.title_must_exclude else "-"
        if len(s.filters.title_must_exclude) > 3:
            excludes += f" (+{len(s.filters.title_must_exclude)-3})"
        profiles_table.add_row(s.name, s.keywords, s.location, s.date_posted, status, excludes)

    console.print(profiles_table)


def main():
    parser = argparse.ArgumentParser(
        description="LinkedIn Job Alert Bot - Scrapes jobs with custom filters and sends Discord webhook alerts.",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("-c", "--config", default="config.yaml", help="Path to config.yaml (default: config.yaml)")
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable verbose debug logging")

    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # Command: run (daemon mode)
    sub_run = subparsers.add_parser("run", help="Start continuous monitoring daemon")

    # Command: scan-once
    sub_scan = subparsers.add_parser("scan-once", help="Run a single scan cycle and exit")

    # Command: test-webhook
    sub_test = subparsers.add_parser("test-webhook", help="Send a test message to Discord webhook")
    sub_test.add_argument("--url", default=None, help="Custom webhook URL to test (overrides config)")

    # Command: stats
    sub_stats = subparsers.add_parser("stats", help="Show database job count and scan stats")

    # Command: reset-db
    sub_reset = subparsers.add_parser("reset-db", help="Clear all stored jobs and scan history")
    sub_reset.add_argument("-y", "--yes", action="store_true", help="Skip confirmation prompt")

    # Command: validate
    sub_validate = subparsers.add_parser("validate", help="Validate config.yaml and view active search profiles")

    args = parser.parse_args()

    # Load configuration
    try:
        config = load_config(args.config)
    except Exception as e:
        console.print(f"[bold red]Configuration Error:[/bold red] {e}")
        sys.exit(1)

    log_level = "DEBUG" if args.verbose else config.settings.log_level
    setup_logger(log_level)

    # Default to "run" if no subcommand provided
    if not args.command or args.command == "run":
        cmd_run(args, config)
    elif args.command == "scan-once":
        cmd_scan_once(args, config)
    elif args.command == "test-webhook":
        cmd_test_webhook(args, config)
    elif args.command == "stats":
        cmd_stats(args, config)
    elif args.command == "reset-db":
        cmd_reset_db(args, config)
    elif args.command == "validate":
        cmd_validate(args, config)


if __name__ == "__main__":
    main()
