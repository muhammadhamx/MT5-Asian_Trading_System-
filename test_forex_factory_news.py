"""
Test script to demonstrate Forex Factory news integration for XAUUSD
Shows the exact response format and how we process it
"""

import requests
import json
from datetime import datetime, timedelta
import pytz

def test_forex_factory_response():
    """Test Forex Factory API and show response format"""
    print("=" * 60)
    print("FOREX FACTORY NEWS INTEGRATION TEST")
    print("=" * 60)
    
    try:
        # Forex Factory calendar URL (free)
        url = "https://nfs.faireconomy.media/ff_calendar_thisweek.json"
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        
        print(f"[INFO] Fetching from: {url}")
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        
        data = response.json()
        print(f"[SUCCESS] Response received: {len(data)} total events")
        
        # Show sample response format
        if data:
            print("\n[SAMPLE] FOREX FACTORY RESPONSE FORMAT:")
            sample_event = data[0]
            print(json.dumps(sample_event, indent=2))
        
        # Filter for USD events only (for XAUUSD trading)
        usd_events = []
        tier1_keywords = ['FOMC', 'CPI', 'NFP', 'INTEREST_RATE', 'GDP', 'UNEMPLOYMENT']
        
        for event in data:
            currency = event.get('currency', '').upper()
            if currency == 'USD':
                title = event.get('title', '').upper()
                impact = event.get('impact', '').upper()
                
                # Check if it's a Tier 1 event
                is_tier1 = any(keyword in title for keyword in tier1_keywords)
                
                # Only include HIGH/MEDIUM impact or Tier 1 events
                if impact in ['HIGH', 'MEDIUM'] or is_tier1:
                    usd_events.append({
                        'title': event.get('title', ''),
                        'date': event.get('date', ''),
                        'time': event.get('time', ''),
                        'impact': impact,
                        'tier': 'TIER1' if is_tier1 else 'OTHER',
                        'forecast': event.get('forecast', ''),
                        'previous': event.get('previous', ''),
                        'actual': event.get('actual', '')
                    })
        
        print(f"\n[USD] USD EVENTS FOR XAUUSD TRADING: {len(usd_events)} events")
        print("-" * 60)
        
        if usd_events:
            for i, event in enumerate(usd_events[:5], 1):  # Show first 5
                tier_indicator = "[T1]" if event['tier'] == 'TIER1' else "[HI]"
                print(f"{i}. {tier_indicator} {event['date']} {event['time']} - {event['title']}")
                print(f"   Impact: {event['impact']}, Forecast: {event['forecast']}, Previous: {event['previous']}")
                print()
        else:
            print("No USD high-impact events found in the current data")
        
        print("\n[USAGE] HOW WE USE THIS FOR XAUUSD:")
        print("1. Filter for USD events only (affects gold prices)")
        print("2. Classify as TIER1 (60min buffer) or OTHER (30min buffer)")
        print("3. Block trading during buffer windows")
        print("4. Store in database for real-time blackout checks")
        
        return True
        
    except Exception as e:
        print(f"[ERROR] Error: {e}")
        return False

if __name__ == "__main__":
    test_forex_factory_response()