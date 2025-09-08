"""
Django management command to fetch real-time economic news
Usage: python manage.py fetch_news
"""

from django.core.management.base import BaseCommand
from django.utils import timezone
from mt5_integration.services.news_feed_service import NewsFeedService
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Fetch real-time economic news from multiple providers'

    def add_arguments(self, parser):
        parser.add_argument(
            '--hours-ahead',
            type=int,
            default=24,
            help='Number of hours ahead to fetch news (default: 24)'
        )
        parser.add_argument(
            '--cleanup',
            action='store_true',
            help='Clean up old news events (older than 7 days)'
        )
        parser.add_argument(
            '--verbose',
            action='store_true',
            help='Enable verbose output'
        )

    def handle(self, *args, **options):
        self.stdout.write(
            self.style.SUCCESS(
                f'[INFO] Starting news feed update at {timezone.now().strftime("%Y-%m-%d %H:%M:%S")}'
            )
        )

        # Initialize news service
        news_service = NewsFeedService()

        try:
            # Fetch news updates
            hours_ahead = options['hours_ahead']
            result = news_service.fetch_news_updates(hours_ahead)

            if result['success']:
                self.stdout.write(
                    self.style.SUCCESS(
                        f'[SUCCESS] News update completed successfully!'
                    )
                )
                self.stdout.write(f'   Total events fetched: {result["total_fetched"]}')
                self.stdout.write(f'   Unique events: {result["unique_events"]}')
                self.stdout.write(f'   Events stored: {result["stored_events"]}')
                self.stdout.write(f'   Provider used: {result["provider"]}')

            else:
                self.stdout.write(
                    self.style.ERROR(f'[ERROR] News update failed: {result.get("error", "Unknown error")}')
                )

            # Show upcoming high-impact events
            upcoming_events = news_service.get_upcoming_events(hours_ahead=4)
            if upcoming_events:
                self.stdout.write(
                    self.style.SUCCESS(f'\n[INFO] Upcoming high-impact events (next 4 hours):')
                )
                for event in upcoming_events[:10]:  # Show top 10
                    time_str = event['release_time'].strftime('%H:%M')
                    tier_indicator = '[T1]' if event['tier'] == 'TIER1' else '[HI]'
                    self.stdout.write(
                        f'   {tier_indicator} {time_str} {event["currency"]} - {event["event_name"]} '
                        f'({event["minutes_until"]}min, {event["required_buffer"]}min buffer)'
                    )
            else:
                self.stdout.write('[INFO] No high-impact events in the next 4 hours')

            # Cleanup old events if requested
            if options['cleanup']:
                self.stdout.write('\n[INFO] Cleaning up old events...')
                deleted_count = news_service.cleanup_old_events()
                self.stdout.write(
                    self.style.SUCCESS(f'   [SUCCESS] Cleaned up {deleted_count} old events')
                )

        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'[ERROR] Critical error during news update: {str(e)}')
            )
            logger.error(f'Critical error in fetch_news command: {e}', exc_info=True)

        self.stdout.write(
            self.style.SUCCESS(
                f'\n[COMPLETE] News feed update completed at {timezone.now().strftime("%Y-%m-%d %H:%M:%S")}'
            )
        )