from django.test import TestCase
from mt5_integration.models.confluence_check import ConfluenceCheck
from mt5_integration.models.trading_session import TradingSession
from django.utils import timezone

class ConfluenceCheckModelTest(TestCase):
    def setUp(self):
        self.session = TradingSession.objects.create(
            session_date=timezone.now().date(),
            session_type='ASIAN',
            current_state='IDLE'
        )

    def test_confluence_check_creation(self):
        confluence = ConfluenceCheck.objects.create(
            session=self.session,
            timeframe='M15',
            bias='BULL',
            trend_strength=25.0,
            atr_value=2.5,
            adx_value=30.0,
            spread=1.2,
            velocity_spike=True,
            news_risk=False,
            news_buffer_minutes=60,
            passed=True
        )
        self.assertEqual(confluence.timeframe, 'M15')
        self.assertEqual(confluence.bias, 'BULL')
        self.assertTrue(confluence.velocity_spike)
        self.assertFalse(confluence.news_risk)
        self.assertTrue(confluence.passed)
