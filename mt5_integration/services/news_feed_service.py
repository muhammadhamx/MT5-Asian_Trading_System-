"""
Real-time News Feed Integration Service
Supports multiple news providers with fallback mechanisms
"""

import os
import requests
import logging
from datetime import datetime, timedelta
from django.utils import timezone
from typing import Dict, List, Optional, Tuple
from dotenv import load_dotenv
from ..models import EconomicNews

# Load environment variables
load_dotenv()

logger = logging.getLogger(__name__)


class NewsFeedService:
    """Real-time economic news feed integration with multiple providers"""
    
    def __init__(self):
        # Only use Forex Factory (free)
        self.forex_factory_enabled = True
        
        # Tier 1 events (require ≥60 min buffer per client spec)
        self.tier1_events = [
            'FOMC', 'CPI', 'NFP', 'INTEREST_RATE_DECISION', 'EMPLOYMENT_CHANGE',
            'GDP', 'INFLATION_RATE', 'UNEMPLOYMENT_RATE', 'RETAIL_SALES',
            'MANUFACTURING_PMI', 'SERVICES_PMI', 'CONSUMER_CONFIDENCE'
        ]
        
        # Focus on USD only for XAUUSD trading
        self.priority_currencies = ['USD']
        
    def fetch_news_updates(self, hours_ahead: int = 24) -> Dict:
        """Fetch USD news updates from Forex Factory (free)"""
        try:
            # Only use Forex Factory
            news_data = self._fetch_forex_factory_news(hours_ahead)
            
            if not news_data:
                logger.warning("No news data fetched from Forex Factory")
                return {
                    'success': True,
                    'total_fetched': 0,
                    'unique_events': 0,
                    'stored_events': 0,
                    'provider': 'forex_factory'
                }
            
            logger.info(f"Fetched {len(news_data)} USD events from Forex Factory")
            
            # Sort by time
            sorted_news = sorted(news_data, key=lambda x: x['release_time'])
            
            # Store in database
            stored_count = self._store_news_events(sorted_news)
            
            return {
                'success': True,
                'total_fetched': len(news_data),
                'unique_events': len(news_data),
                'stored_events': stored_count,
                'provider': 'forex_factory'
            }
            
        except Exception as e:
            logger.error(f"Critical error in fetch_news_updates: {e}")
            return {
                'success': False,
                'error': str(e),
                'total_fetched': 0,
                'unique_events': 0,
                'stored_events': 0
            }
    
    def _fetch_forex_factory_news(self, hours_ahead: int) -> List[Dict]:
        """Fetch news from Forex Factory (free, no API key required)"""
        try:
            # Forex Factory calendar URL (unofficial API)
            url = "https://nfs.faireconomy.media/ff_calendar_thisweek.json"
            
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            news_events = []
            
            now = timezone.now()
            cutoff_time = now + timedelta(hours=hours_ahead)
            
            for event in data:
                try:
                    # Only process USD events for XAUUSD trading
                    currency = event.get('currency', '').upper()
                    if currency != 'USD':
                        continue
                    
                    # Parse event time - handle multiple formats
                    date_str = event.get('date', '')
                    time_str = event.get('time', '')
                    
                    if not date_str or not time_str:
                        continue
                    
                    # Try different datetime formats
                    event_time = None
                    datetime_formats = [
                        '%m-%d-%Y %I:%M%p',  # Original format
                        '%Y-%m-%dT%H:%M:%S%z',  # ISO format with timezone
                        '%Y-%m-%d %H:%M:%S',  # Simple format
                    ]
                    
                    event_time_str = f"{date_str} {time_str}".strip()
                    
                    for fmt in datetime_formats:
                        try:
                            if 'T' in event_time_str and '%z' in fmt:
                                # Handle timezone format
                                event_time = datetime.fromisoformat(event_time_str.replace('Z', '+00:00'))
                            else:
                                event_time = datetime.strptime(event_time_str, fmt)
                                event_time = timezone.make_aware(event_time)
                            break
                        except ValueError:
                            continue
                    
                    if not event_time:
                        logger.debug(f"Could not parse time: {event_time_str}")
                        continue
                    
                    # Filter by time window
                    if event_time < now or event_time > cutoff_time:
                        continue
                    
                    # Map impact to severity
                    impact = event.get('impact', '').upper()
                    severity_map = {
                        'HIGH': 'HIGH',
                        'MEDIUM': 'MEDIUM',
                        'LOW': 'LOW',
                        'NON-ECONOMIC': 'LOW'
                    }
                    severity = severity_map.get(impact, 'MEDIUM')
                    
                    # Check if it's a Tier 1 event
                    event_name = event.get('title', '').upper()
                    is_tier1 = any(tier1 in event_name for tier1 in self.tier1_events)
                    
                    # Only include HIGH/MEDIUM impact or Tier 1 events
                    if severity == 'LOW' and not is_tier1:
                        continue
                    
                    news_events.append({
                        'event_name': event.get('title', ''),
                        'currency': 'USD',
                        'severity': severity,
                        'tier': 'TIER1' if is_tier1 else 'OTHER',
                        'release_time': event_time,
                        'actual_value': event.get('actual', ''),
                        'forecast_value': event.get('forecast', ''),
                        'previous_value': event.get('previous', ''),
                        'description': f"USD Economic Event: {event.get('title', '')}",
                        'source': 'forex_factory'
                    })
                    
                except Exception as e:
                    logger.debug(f"Error parsing Forex Factory event: {e}")
                    continue
            
            return news_events
            
        except Exception as e:
            logger.error(f"Error fetching Forex Factory news: {e}")
            return []
    
    # Removed unused provider methods - only using Forex Factory
    
    def _store_news_events(self, news_events: List[Dict]) -> int:
        """Store news events in database, avoiding duplicates"""
        stored_count = 0
        
        for event_data in news_events:
            try:
                # Check if event already exists
                existing = EconomicNews.objects.filter(
                    event_name=event_data['event_name'],
                    currency=event_data['currency'],
                    release_time=event_data['release_time']
                ).first()
                
                if existing:
                    # Update existing event
                    for key, value in event_data.items():
                        if key != 'source':  # Don't overwrite source
                            setattr(existing, key, value)
                    existing.save()
                else:
                    # Create new event
                    EconomicNews.objects.create(**{
                        k: v for k, v in event_data.items() if k != 'source'
                    })
                    stored_count += 1
                    
            except Exception as e:
                logger.error(f"Error storing news event: {e}")
                continue
        
        return stored_count
    
    def get_upcoming_events(self, hours_ahead: int = 4) -> List[Dict]:
        """Get upcoming high-impact events from database"""
        try:
            now = timezone.now()
            cutoff_time = now + timedelta(hours=hours_ahead)
            
            events = EconomicNews.objects.filter(
                release_time__gte=now,
                release_time__lte=cutoff_time,
                severity__in=['HIGH', 'CRITICAL']
            ).order_by('release_time')
            
            return [
                {
                    'event_name': event.event_name,
                    'currency': event.currency,
                    'severity': event.severity,
                    'tier': event.tier,
                    'release_time': event.release_time,
                    'minutes_until': int((event.release_time - now).total_seconds() / 60),
                    'required_buffer': event.get_required_buffer_minutes()
                }
                for event in events
            ]
            
        except Exception as e:
            logger.error(f"Error getting upcoming events: {e}")
            return []
    
    def cleanup_old_events(self, days_old: int = 7):
        """Clean up old news events from database"""
        try:
            cutoff_date = timezone.now() - timedelta(days=days_old)
            deleted_count = EconomicNews.objects.filter(
                release_time__lt=cutoff_date
            ).delete()[0]
            
            logger.info(f"Cleaned up {deleted_count} old news events")
            return deleted_count
            
        except Exception as e:
            logger.error(f"Error cleaning up old events: {e}")
            return 0